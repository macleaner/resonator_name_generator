#!/usr/bin/env python3
"""Build the word lists that resonators are named from.

Every list is normalised to plain ASCII single tokens, filtered against
``blocklist.txt``/``blockpatterns.txt``, and written one word per line:

  * ``names.txt`` -- human given names from around the world. Wikidata given-name
    items (CC0) supply the breadth; ``popular-names-by-country-dataset`` (CC0)
    and the US SSA baby names (public domain) make sure the common names are
    there and not just the long tail.
  * ``pet_names.txt`` -- names from the Seattle and New York City pet licence
    registers (open data), minus any that are also human given names, which is
    what leaves the Biscuits and Noodles.
  * ``nouns_en.txt``, ``nouns_es.txt``, ``nouns_nl.txt`` -- concrete, picturable
    common nouns (foods, drinks, instruments, clothes, furniture, vehicles,
    plants, and species) from Wikidata (CC0).

Usage::

    python tools/build_names.py                  # reuse cached downloads
    python tools/build_names.py --refresh        # re-download every source
    python tools/build_names.py --only nouns_nl
    python tools/build_names.py --show-excluded

The lists are written into ``resonator_name_generator/data/`` so they ship with
the package. Downloads are cached under ``build_cache/``, which is not meant to be
committed; re-runs after the first are fully offline.

Both endpoints throttle scripted access and can fail while still returning HTTP
200, so every response is integrity-checked before it is cached and retried with
backoff -- a truncated reply must never be cached as if it were complete.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "build_cache"
OUT_DIR = ROOT / "resonator_name_generator" / "data"
MANIFEST_PATH = OUT_DIR / "manifest.json"
BLOCKLIST_PATH = Path(__file__).resolve().parent / "blocklist.txt"
BLOCKPATTERNS_PATH = Path(__file__).resolve().parent / "blockpatterns.txt"

USER_AGENT = "resonator-name-generator/0.1 (random detector names)"

# A name has to survive all of this to make it into the list. The limits are set
# for names that end up in filenames, log lines, and plot legends.
MIN_LEN = 3
MAX_LEN = 12
VOWELS = set("aeiouy")

FORENAMES_CSV_URL = (
    "https://raw.githubusercontent.com/sigpwned/popular-names-by-country-dataset"
    "/main/common-forenames-by-country.csv"
)
SSA_URL = "https://raw.githubusercontent.com/hackerb9/ssa-baby-names/master/atleast100.txt"

# QLever's public Wikidata endpoint, not query.wikidata.org. It serves the same
# CC0 Wikidata data and answers this query in about 10 s, where WDQS cannot
# answer it at all: WDQS enforces a 60 s timeout, and past it truncates the
# response mid-stream with a Java stack trace appended to an HTTP 200 body. Even
# sharded into 15 sub-queries it needed ~20 min, and during service incidents it
# drops to 1 request/min with Retry-After: 1000.
QLEVER_URL = "https://qlever.dev/api/wikidata"

SPARQL_PREFIXES = (
    "PREFIX wd: <http://www.wikidata.org/entity/> "
    "PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
)

# instance-of classes: male given name, female given name, unisex given name
WD_CLASSES = ("Q12308941", "Q11879590", "Q3409032")

# Label languages to accept, all Latin-script, spanning Europe, Africa,
# South-East Asia, and the Turkic world. Restricting to these keeps the download
# to ~11 MB; labels in other scripts would be dropped by normalise() anyway.
WD_LANGS = (
    "en de fr es pt it nl pl tr id sw vi hu ro cs sv fi da nb hr sl sq eu ca gl "
    "is af so ms tl yo ha zu az uz et lv lt"
).split()

# How long to wait out an HTTP 429 that arrives without a Retry-After header.
RATE_LIMIT_WAIT = 65.0

# Letters that NFKD does not decompose into ASCII plus combining marks.
TRANSLITERATE = str.maketrans(
    {
        "ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
        "ß": "ss", "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th", "đ": "d",
        "Đ": "D", "ł": "l", "Ł": "L", "ħ": "h", "Ħ": "H", "ı": "i",
        "İ": "I", "ŋ": "ng", "Ŋ": "Ng", "ə": "e", "Ə": "E", "ʻ": "",
        "ʼ": "", "'": "", "’": "",
    }
)


# --------------------------------------------------------------------------- #
# fetching
# --------------------------------------------------------------------------- #

class Incomplete(Exception):
    """A response arrived but failed its integrity check."""


def _get(url: str, *, accept: str | None = None, attempts: int = 8) -> bytes:
    """GET ``url``, backing off on the throttling both endpoints apply."""
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    delay = 5.0
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (
                403, 429, 500, 502, 503, 504,
            )
            if not retryable or attempt == attempts:
                raise
            wait = delay
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                # Retrying inside the window just burns another request against
                # the limit, so wait out the full window unless told otherwise.
                retry_after = (exc.headers or {}).get("Retry-After", "").strip()
                wait = float(retry_after) if retry_after.isdigit() else max(delay, RATE_LIMIT_WAIT)
            print(f"  {exc} -- retrying in {wait:.0f}s", file=sys.stderr)
        time.sleep(wait)
        delay *= 2
    raise RuntimeError(f"gave up on {url}")


def cached(
    filename: str,
    url: str,
    *,
    refresh: bool,
    validate: Callable[[bytes], None] | None = None,
    accept: str | None = None,
) -> str:
    """Return the body of ``url``, downloading into the cache when needed.

    ``validate`` should raise :class:`Incomplete` for a body that is malformed or
    truncated; such a response is retried rather than cached, and a cached file
    that no longer validates is re-fetched.
    """
    path = CACHE_DIR / filename
    if not refresh and path.exists():
        data = path.read_bytes()
        try:
            if validate is not None:
                validate(data)
            return data.decode("utf-8-sig")
        except Incomplete as exc:
            print(f"  cached {filename} is unusable ({exc}); re-fetching")

    print(f"fetching {filename}")
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""
    for attempt in range(1, 4):
        data = _get(url, accept=accept)
        try:
            if validate is not None:
                validate(data)
        except Incomplete as exc:
            last_error = str(exc)
            print(f"  attempt {attempt}: {exc}; retrying", file=sys.stderr)
            time.sleep(10.0 * attempt)
            continue
        path.write_bytes(data)
        return data.decode("utf-8-sig")
    raise RuntimeError(f"no complete response for {filename}: {last_error}")


def _validate_csv(header: str, expected_rows: int | None = None) -> Callable[[bytes], None]:
    """Reject the several ways a SPARQL endpoint fails while still returning 200.

    A timed-out query yields a partial body with a stack trace appended, an
    overloaded one yields an HTML error page, and a stream cut at a buffer
    boundary simply stops mid-name. Where the expected row count is known from a
    companion COUNT query, that is checked too -- which turns "looks plausible"
    into "provably complete".
    """

    def validate(data: bytes) -> None:
        head = data[:400].lower()
        if b"exception" in data.lower() or b"<html" in head or head.startswith(b"{"):
            # QLever reports query timeouts as a JSON body with an "exception"
            # key, still under HTTP 200.
            raise Incomplete(f"error page or stack trace in body ({len(data)} bytes)")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Incomplete("not UTF-8") from exc
        if not text.startswith(f"{header}\n"):
            raise Incomplete(f"missing CSV header {header!r} (starts {data[:40]!r})")
        if not text.endswith("\n"):
            raise Incomplete(f"body ends mid-row ({len(data)} bytes)")
        rows = sum(1 for _ in csv.reader(io.StringIO(text))) - 1
        if rows < 1:
            raise Incomplete("no result rows")
        if expected_rows is not None and rows != expected_rows:
            raise Incomplete(f"{rows} rows, but COUNT said {expected_rows}")

    return validate


def _validate_text(marker: str) -> Callable[[bytes], None]:
    def validate(data: bytes) -> None:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise Incomplete("not UTF-8") from exc
        first_line = text.splitlines()[0] if text else ""
        if marker not in first_line:
            raise Incomplete(f"first line does not contain {marker!r}")
    return validate


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #

def _sparql_url(query: str) -> str:
    # CSV must be negotiated with an Accept header; a ?format=csv parameter is
    # ignored and answered with SPARQL XML instead.
    return f"{QLEVER_URL}?{urllib.parse.urlencode({'query': SPARQL_PREFIXES + query})}"


def source_wikidata(refresh: bool) -> list[str]:
    """Latin-script labels of every Wikidata item that is a given name."""
    classes = " ".join(f"wd:{cls}" for cls in WD_CLASSES)
    langs = ", ".join(f"'{lang}'" for lang in WD_LANGS)
    body = (
        f" VALUES ?cls {{ {classes} }}"
        " ?n wdt:P31 ?cls ."
        " ?n rdfs:label ?label ."
        f" FILTER(LANG(?label) IN ({langs}))"
    )

    # The COUNT is fetched first so the bulk download can be checked against it.
    count_text = cached(
        "wikidata-label-count.csv",
        _sparql_url(f"SELECT (COUNT(DISTINCT ?label) AS ?c) WHERE {{{body} }}"),
        refresh=refresh,
        validate=_validate_csv("c"),
        accept="text/csv",
    )
    expected = int(count_text.splitlines()[1])

    text = cached(
        "wikidata-labels.csv",
        _sparql_url(f"SELECT DISTINCT ?label WHERE {{{body} }}"),
        refresh=refresh,
        validate=_validate_csv("label", expected_rows=expected),
        accept="text/csv",
    )
    rows = [row[0] for row in csv.reader(io.StringIO(text)) if row][1:]
    print(f"  wikidata: {len(rows)} labels (COUNT agreed)")
    return rows


def source_popular_by_country(refresh: bool) -> list[str]:
    """Romanised forms of the most popular given names in 106 countries."""
    text = cached(
        "popular-forenames-by-country.csv",
        FORENAMES_CSV_URL,
        refresh=refresh,
        validate=_validate_text("Romanized Name"),
    )
    reader = csv.DictReader(io.StringIO(text))
    return [row["Romanized Name"] for row in reader if row.get("Romanized Name")]


def source_ssa(refresh: bool) -> list[str]:
    """US names recorded at least 100 times in a single year since 1880."""
    text = cached("ssa-atleast100.txt", SSA_URL, refresh=refresh)
    if "Too Many Requests" in text[:200]:
        raise RuntimeError("raw.githubusercontent throttled the SSA download; retry later")
    return text.split()


NAME_SOURCES: dict[str, tuple[Callable[[bool], list[str]], str]] = {
    "wikidata": (source_wikidata, "https://qlever.dev/api/wikidata (Wikidata, CC0)"),
    "popular-by-country": (
        source_popular_by_country,
        "https://github.com/sigpwned/popular-names-by-country-dataset (CC0)",
    ),
    "ssa": (source_ssa, "https://github.com/hackerb9/ssa-baby-names (public domain)"),
}


# --------------------------------------------------------------------------- #
# pet names
# --------------------------------------------------------------------------- #

# City pet-licence registers, read through Socrata's aggregation API so the
# server does the counting. The minimum occurrence count is a quality gate: it
# drops typos and one-off joke names while keeping names real people actually
# used. NYC is much larger than Seattle, hence the higher floor.
PET_SOURCES = (
    # label, endpoint, name column, minimum occurrences
    ("seattle-pets", "https://data.seattle.gov/resource/jguv-t9rb.csv", "animal_s_name", 3),
    ("nyc-dogs", "https://data.cityofnewyork.us/resource/nu7n-tubp.csv", "animalname", 25),
)

# Registry placeholders, not names. Multi-word forms ("NAME NOT PROVIDED") are
# already dropped by normalise(); these are the single-token ones.
PET_PLACEHOLDERS = frozenset(
    """unknown unknow none null nil nan noname nameless unnamed notprovided
    nonamegiven dog dogs cat cats puppy kitten pet pets animal name test
    xxx tbd""".split()
)


def source_pet_register(
    label: str, endpoint: str, column: str, min_count: int
) -> Callable[[bool], list[str]]:
    """Build a source that reads one city's pet-licence name frequencies."""

    def fetch(refresh: bool) -> list[str]:
        query = urllib.parse.urlencode(
            {
                "$select": f"{column},count(*) as n",
                "$group": column,
                "$order": "n desc",
                "$limit": 50000,
            }
        )
        text = cached(
            f"{label}.csv",
            f"{endpoint}?{query}",
            refresh=refresh,
            validate=_validate_text(column),
        )
        names = []
        for row in csv.DictReader(io.StringIO(text)):
            raw, count = row.get(column) or "", row.get("n") or "0"
            if raw.strip().lower().replace(" ", "") in PET_PLACEHOLDERS:
                continue
            if int(count) >= min_count:
                names.append(raw)
        print(f"  {label}: {len(names)} names with >= {min_count} licences")
        return names

    return fetch


PET_NAME_SOURCES: dict[str, tuple[Callable[[bool], list[str]], str]] = {
    label: (source_pet_register(label, endpoint, column, floor), f"{endpoint} (open data)")
    for label, endpoint, column, floor in PET_SOURCES
}


# --------------------------------------------------------------------------- #
# common nouns
# --------------------------------------------------------------------------- #

# Wikidata classes whose members are the kind of concrete, picturable thing that
# raises a smile on a plot legend: foods, drinks, instruments, clothes,
# furniture, vehicles, plants. Traversed with P279* (subclass of), which yields
# *classes* of things -- "waffle", "trombone" -- rather than P31 instances, which
# would yield individual products and brands.
#
# Deliberately excluded after inspecting what they return:
#   Q11422 toy        -- Wikidata files sex toys under it
#   Q987767 container -- pulls in cluster bombs and other munitions
#   Q39546 tool       -- mostly technical instruments, little whimsy
#   Q729 animal       -- subclass chains reach human social roles (widow,
#                        castrato, gladiatrix) rather than animals; real animals
#                        come from the species query below instead
WHIMSY_CLASSES = {
    "Q2095": "food",
    "Q40050": "drink",
    "Q34379": "musical-instrument",
    "Q11460": "clothing",
    "Q14745": "furniture",
    "Q42889": "vehicle",
    "Q756": "plant",
}

# Vernacular species names -- aardvarken, koboldhaai, narwhal. Taxa are P31
# instances of taxon rather than P279 subclasses, and restricting to species rank
# keeps the everyday names and skips higher taxonomic ranks.
SPECIES_QUERY = (
    " ?i wdt:P31 wd:Q16521 . ?i wdt:P105 wd:Q7432 . ?i rdfs:label ?label ."
)

# Common nouns are lowercase in Wikidata labels where brands and proper nouns are
# capitalised, so requiring a lowercase initial drops Vegemite, Altoids, and
# Marsala while keeping stroopwafel and paksoi. Applying the length and
# single-token limits server-side matters too: for the species query it turns a
# 64 MB download into 14 kB.
NOUN_LABEL_FILTER = (
    r"FILTER(REGEX(STR(?label), '^\\p{Ll}{" + f"{MIN_LEN},{MAX_LEN}" + r"}$'))"
)

NOUN_LANGUAGES = {"en": "English", "es": "Spanish", "nl": "Dutch"}

# Wikidata labels a regional food or garment with its native name in every
# language, so the raw English list arrives full of words that are not English
# (Yakimochi, Xeremia, Joelho -- Portuguese for knee) and the Spanish list full of
# words that are not Spanish (Rohwurst, Nabemono, Ontbijtkoek). Each language's
# nouns are therefore intersected with a general wordlist for that language,
# which is used only as a build-time membership test.
#
# The trade is precision over recall, and it is not free: Dutch builds compounds
# productively, so no fixed lexicon lists all of them and genuine words like
# Monniksgier and Fluitzwaan are lost along with the foreign ones. Guaranteeing
# that every entry really is a word in the language seemed worth more than the
# extra few thousand entries. All three lists are permissively licensed --
# public domain, CC0, and BSD/CC-BY respectively, with no share-alike.
NOUN_DICTIONARIES = {
    "en": (
        "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
        "https://github.com/dwyl/english-words (Unlicense)",
    ),
    "es": (
        "https://raw.githubusercontent.com/lorenbrichter/Words/master/Words/es.txt",
        "https://github.com/lorenbrichter/Words (CC0)",
    ),
    "nl": (
        "https://raw.githubusercontent.com/OpenTaal/opentaal-wordlist/master/wordlist.txt",
        "https://github.com/OpenTaal/opentaal-wordlist (Revised BSD / CC BY 3.0)",
    ),
}


def dictionary_words(lang: str) -> Callable[[bool], frozenset[str]]:
    """Build a loader for the set of words attested in ``lang``."""

    def load(refresh: bool) -> frozenset[str]:
        url, _ = NOUN_DICTIONARIES[lang]
        text = cached(f"dictionary-{lang}.txt", url, refresh=refresh)
        # Normalising both sides means an unaccented dictionary still matches an
        # accented label: catamarán and catamaran fold to the same key.
        words = {w.lower() for w in (normalise(raw) for raw in text.split()) if w}
        print(f"  dictionary:{lang} {len(words)} words")
        return frozenset(words)

    return load


def source_nouns(lang: str) -> Callable[[bool], list[str]]:
    """Build a source that reads whimsical common nouns in one language."""

    def fetch(refresh: bool) -> list[str]:
        queries = {
            topic: f" ?i wdt:P279* wd:{qid} . ?i rdfs:label ?label ."
            for qid, topic in WHIMSY_CLASSES.items()
        }
        queries["species"] = SPECIES_QUERY

        words: list[str] = []
        for topic, body in queries.items():
            query = (
                f"SELECT DISTINCT ?label WHERE {{{body}"
                f" FILTER(LANG(?label) = '{lang}') {NOUN_LABEL_FILTER} }}"
            )
            text = cached(
                f"nouns-{lang}-{topic}.csv",
                _sparql_url(query),
                refresh=refresh,
                validate=_validate_csv("label"),
                accept="text/csv",
            )
            rows = [row[0] for row in csv.reader(io.StringIO(text)) if row][1:]
            print(f"  nouns:{lang} {topic}: {len(rows)}")
            words.extend(rows)
        return words

    return fetch


def noun_sources(lang: str) -> dict[str, tuple[Callable[[bool], list[str]], str]]:
    return {
        f"wikidata-{lang}": (
            source_nouns(lang),
            "https://qlever.dev/api/wikidata (Wikidata, CC0)",
        )
    }


# --------------------------------------------------------------------------- #
# normalisation and filtering
# --------------------------------------------------------------------------- #

def normalise(raw: str) -> str | None:
    """Fold ``raw`` to a plain-ASCII single token, or return None to drop it.

    Diacritics are stripped rather than rejected, so Tünde becomes Tunde and
    Martí becomes Marti. Anything left holding a non-letter -- a space, hyphen,
    apostrophe, digit, or parenthesised Wikidata disambiguator -- is dropped,
    because resonator names need to work as bare identifiers.
    """
    name = unicodedata.normalize("NFKC", raw).strip().translate(TRANSLITERATE)
    name = "".join(
        ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)
    )
    if not name.isascii() or not name.isalpha():
        return None
    if not MIN_LEN <= len(name) <= MAX_LEN:
        return None
    lowered = name.lower()
    if not VOWELS & set(lowered):
        return None
    if re.search(r"(.)\1\1", lowered):  # Aaaa, and similar scrape artefacts
        return None
    return lowered.capitalize()


def load_blocklist() -> tuple[set[str], list[re.Pattern[str]]]:
    def entries(path: Path) -> list[str]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [s for s in (line.split("#", 1)[0].strip() for line in lines) if s]

    exact = {entry.lower() for entry in entries(BLOCKLIST_PATH)}
    patterns = [re.compile(p, re.IGNORECASE) for p in entries(BLOCKPATTERNS_PATH)]
    return exact, patterns


class Corpus:
    """One output word list, built from one or more sources."""

    def __init__(
        self,
        filename: str,
        description: str,
        sources: dict[str, tuple[Callable[[bool], list[str]], str]],
        exclude_from: str | None = None,
        restrict_to: Callable[[bool], frozenset[str]] | None = None,
        restrict_note: str | None = None,
    ) -> None:
        self.filename = filename
        self.description = description
        self.sources = sources
        # Name of another corpus whose entries should be held back. Pet names use
        # this: dropping the ones that are ordinary human given names is what
        # leaves Biscuit and Noodle rather than another copy of Bella and Max.
        self.exclude_from = exclude_from
        # Optional wordlist every entry must appear in; see NOUN_DICTIONARIES.
        self.restrict_to = restrict_to
        self.restrict_note = restrict_note
        self.words: list[str] = []
        self.excluded: list[str] = []
        self.unattested = 0
        self.per_source: dict[str, int] = {}


CORPORA = {
    "names": Corpus("names.txt", "human given names from around the world", NAME_SOURCES),
    "pet_names": Corpus(
        "pet_names.txt",
        "pet names that are not also human given names",
        PET_NAME_SOURCES,
        exclude_from="names",
    ),
    **{
        f"nouns_{lang}": Corpus(
            f"nouns_{lang}.txt",
            f"whimsical {name} common nouns",
            noun_sources(lang),
            restrict_to=dictionary_words(lang),
            restrict_note=NOUN_DICTIONARIES[lang][1],
        )
        for lang, name in NOUN_LANGUAGES.items()
    },
}


def build_corpus(corpus: Corpus, refresh: bool, holdback: frozenset[str]) -> None:
    exact, patterns = load_blocklist()
    attested = corpus.restrict_to(refresh) if corpus.restrict_to else None
    kept: dict[str, str] = {}          # lowercase key -> canonical casing
    excluded: set[str] = set()

    for label, (fetch, _) in corpus.sources.items():
        before = len(kept)
        for raw in fetch(refresh):
            word = normalise(raw)
            if word is None:
                continue
            lowered = word.lower()
            if lowered in holdback:
                continue
            if attested is not None and lowered not in attested:
                corpus.unattested += 1
                continue
            if lowered in exact or any(p.search(lowered) for p in patterns):
                excluded.add(word)
                continue
            kept.setdefault(lowered, word)
        corpus.per_source[label] = len(kept) - before
        print(f"  {label}: +{len(kept) - before} new ({len(kept)} total)")

    corpus.words = sorted(kept.values())
    corpus.excluded = sorted(excluded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download all sources")
    parser.add_argument(
        "--only",
        metavar="CORPUS",
        choices=sorted(CORPORA),
        help="build just one list (%(choices)s)",
    )
    parser.add_argument(
        "--show-excluded",
        action="store_true",
        help="print every word the blocklist removed, for reviewing false positives",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wanted = [args.only] if args.only else list(CORPORA)

    for key in wanted:
        corpus = CORPORA[key]
        print(f"\n{key}:")
        holdback: frozenset[str] = frozenset()
        if corpus.exclude_from:
            other = OUT_DIR / CORPORA[corpus.exclude_from].filename
            if not other.exists():
                raise SystemExit(
                    f"{key} needs {other.name}; build {corpus.exclude_from} first"
                )
            holdback = frozenset(w.lower() for w in other.read_text().split())
        build_corpus(corpus, args.refresh, holdback)
        (OUT_DIR / corpus.filename).write_text(
            "\n".join(corpus.words) + "\n", encoding="utf-8"
        )

    built = {key: CORPORA[key] for key in wanted}
    if not args.only:
        MANIFEST_PATH.write_text(
            json.dumps(
                {
                    "generated": date.today().isoformat(),
                    "lists": {
                        key: {
                            "file": corpus.filename,
                            "description": corpus.description,
                            "total": len(corpus.words),
                            "new_per_source": corpus.per_source,
                            "sources": {
                                label: url for label, (_, url) in corpus.sources.items()
                            },
                            "excluded_by_blocklist": len(corpus.excluded),
                            **(
                                {
                                    "restricted_to": corpus.restrict_note,
                                    "dropped_as_unattested": corpus.unattested,
                                }
                                if corpus.restrict_note
                                else {}
                            ),
                        }
                        for key, corpus in built.items()
                    },
                    "filters": {
                        "length": [MIN_LEN, MAX_LEN],
                        "charset": "ASCII letters only, diacritics folded",
                        "blocklist": "tools/blocklist.txt, tools/blockpatterns.txt",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print()
    for key, corpus in built.items():
        print(
            f"wrote {len(corpus.words):6d} to {OUT_DIR.name}/{corpus.filename}"
            f"  ({len(corpus.excluded)} removed by blocklist)"
        )
    if args.show_excluded:
        for key, corpus in built.items():
            if corpus.excluded:
                print(f"\n{key} exclusions:")
                print("\n".join(f"  - {word}" for word in corpus.excluded))
    return 0


if __name__ == "__main__":
    sys.exit(main())
