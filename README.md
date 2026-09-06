# resonator_name_generator

Random names for naming detectors. Intended to be imported by a readout system so
that each resonator gets a memorable name instead of an index.

## Usage

```python
from resonator_name_generator import boring_names, random_name, random_names

random_name()                                  # 'Rosalind'
random_name({"nouns_nl": 1})                   # 'Stroopwafel'
random_names(4, {"names": 4, "pet_names": 1})  # ['Ilinca', 'Tortellini', ...]
random_names(4, {"names": 3, "gibberish": 1})  # ['Ilinca', 'Tavren', ...]
random_names(4, length=6)                      # ['Marnie', 'Kettle', ...]

boring_names(4)                                # ['R0001', 'R0002', ...]
```

`random_names(n)` returns **distinct** names by default — two detectors sharing a
name is worse than no names at all. Pass `unique=False` to allow repeats, and
`avoid=[...]` to skip names already in use.

Both functions take `rng=`, either a `random.Random` or an int seed, so a run can
be reproduced exactly.

### Weighting

`weights` maps a category to a **relative** likelihood; `{"names": 8,
"pet_names": 2}` and `{"names": 4, "pet_names": 1}` mean the same thing. A
category left out of the dict is never drawn, so `{"pet_names": 1}` means "pet
names only".

| Category | Words | Default weight | Share of draws |
| --- | --- | --- | --- |
| `names` | 76,880 | 8.0 | 80% |
| `pet_names` | 1,250 | 1.0 | 10% |
| `nouns_en` | 3,062 | 0.4 | 4% |
| `nouns_es` | 1,427 | 0.3 | 3% |
| `nouns_nl` | 3,072 | 0.3 | 3% |
| `gibberish` | ∞ | 0.0 | — |

The default is tuned so a plot of a few dozen resonators reads as a list of
names with the occasional `Stroopwafel`, rather than as a joke.
`gibberish` is [made up rather than looked up](#pronounceable-gibberish) and is
off by default; it sits in the table at zero because that is a more
discoverable way to say so than leaving it out.

**Weights are per category, not per word** — this is the whole reason the lists
are kept separate. Each draw picks a category by weight, then a word uniformly
inside it. Drawing uniformly from the union instead would give ~90% human names
no matter what you asked for, because `names.txt` is 25× the size of the other
four combined.

If a category runs dry during a unique draw it is dropped and the remaining
weights carry on between them, so `random_names(3000, {"pet_names": 5, "names":
1})` still returns 3,000 names — it just stops being mostly pet names after
1,250. Asking for more than the weighted lists can supply raises `ValueError`
rather than returning a short list.

To eyeball the output:

```bash
python -m resonator_name_generator -n 10 -w nouns_nl=1
```

### Length

Any draw can be held to a length, and it applies to the whole mix — the lists
are filtered to the words that fit and any gibberish is generated to match, so
the result is uniform in width whichever category each name came from:

```python
random_names(4, length=6)        # ['Marnie', 'Kettle', 'Osbert', 'Zonira']
random_names(4, length=(4, 6))   # ['Ilse', 'Marnie', 'Wafel', 'Soat']
```

Pass an exact length or an inclusive `(min, max)` pair. A category with nothing
of that length is dropped up front and its weight passes to the rest, rather
than failing on whichever draw happened to land in it — a length that suits
human names need not suit Dutch compounds. If *nothing* weighted can supply it,
that raises `ValueError`.

The curated lists hold 3 to 12 characters, and thin out fast at the ends: 1,188
names are 3 letters and 264 are 12, against 17,810 at 6. So a narrow length is
worth pairing with a weighted `gibberish`, which never runs out.

```bash
python -m resonator_name_generator -n 10 --length 6 -w names=3 -w gibberish=1
python -m resonator_name_generator -n 10 --length 4-7
```

## Boring mode

Sometimes a memorable name is the wrong answer — a wafer being screened, a
figure that has to sort correctly, a colleague who wants to know which resonator
is which without learning a vocabulary. `boring_names` just counts:

```python
from resonator_name_generator import boring_names

boring_names(3)             # ['R0001', 'R0002', 'R0003']
boring_names(3, "S")        # ['S0001', 'S0002', 'S0003']
boring_names(3, "kid")      # ['kid0001', 'kid0002', 'kid0003']
boring_names(3, start=7)    # ['R0007', 'R0008', 'R0009']
```

The prefix is taken verbatim — `kid` stays lowercase — and must not contain
whitespace or end in a digit, since `R1` + `0001` would be ambiguous. The
counter is zero-padded to a fixed **minimum** `width=4`; a batch that runs past
that widens as a whole rather than in part, because uniform width is what makes
the names line up in a legend and sort correctly in a directory listing:

```python
boring_names(3, start=9999)  # ['R09999', 'R10000', 'R10001']
```

`avoid=[...]` works as it does for a random draw, and matches **exactly**:
nothing is parsed out of the entries, so `R1` does not stand in for `R0001`, and
an entry that is not a name this call would have produced never matches.

```python
boring_names(3, avoid=["Rosalind", "R0001", "R0002"])  # ['R0003', 'R0004', 'R0005']
```

This is a *mode*, not a category: the order matters, nothing is drawn at random,
and there is no weight that mixes it into the word lists — `R0003` between
`Rosalind` and `Stroopwafel` would be neither one thing nor the other. So the
CLI flag takes no weights, and `--length` (an exact one only) sets the width of
the counter rather than filtering anything:

```bash
python -m resonator_name_generator -n 10 --boring
python -m resonator_name_generator -n 10 --boring kid --length 6
```

## Pronounceable gibberish

The `gibberish` category is made up rather than looked up: pronounceable words
of an exact length that are nobody's name. Weight it like any other category to
salt the real words with invented ones —

```python
random_names(6, {"names": 1, "gibberish": 1}, length=6, rng=0)
# ['Pradon', 'Reahus', 'Borles', 'Prachi', 'Saleta', 'Artaud']
```

Three of those are invented, and the point is that you have to check which.
(`Pradon`, `Reahus`, and `Borles`.)

It is off by default (weight `0.0`). For a single word without going through
the weighting, `random_gibberish(length)` is the primitive underneath:

```python
from resonator_name_generator import random_gibberish

random_gibberish(6)  # 'Tavren'
```

### How it works

A word is a run of syllables — *onset* (1–2 consonants, or nothing at the start
of a word), *nucleus* (1–2 vowels), *coda* (0–2 consonants) — each drawn by
weight from an English-ish inventory, so `br` and `st` are possible onsets and
`bt` and `zk` are not.

The length comes out exact without any retrying. The shortest syllable is 2
characters and the next shortest is 3, and every integer above 1 is a sum of 2s
and 3s, so one rule is enough: **never leave exactly one character to fill at a
syllable boundary.** Each unit is drawn from the lengths still compatible with
what remains, and the last syllable lands on the boundary exactly.

What makes the result readable is mostly the junction rules. After a syllable
that ends in a consonant, the next must start with a single one — that caps any
consonant run at three. After one ending in a *stop*, that consonant must be a
liquid, nasal, or glide (`Sidra`, `Abner`; never `Sonksest`). A two-consonant
coda mid-word is restricted to the clusters English actually says, so the only
three-consonant runs the generator can emit are `ndr`, `str`, `ckl`, `mpl` and
26 others like them. Codas are weighted so three syllables in five end on their
vowel, which is the difference between `Tavina` and `Tarvent` — and the
difference is invisible at length 5 and unmissable at length 12, so tune that
weight by reading long ones.

Lengths of 5–9 read best, which is also where about 90% of the real words sit,
so that range is what an unweighted `length` gives you. Below 4 there is no room
for structure (`Kar`, `Bim`), and the space is small enough to exhaust: asking
for 5,000 distinct names at `length=3` raises after the ~3,200 that exist.

### A note on safety

Gibberish passes under nobody's eye before it lands on a plot, so
`syllables.py` carries its own substring filter — separate from the build-time
blocklist in `tools/`, which only ever sees the curated lists. It errs wide on
purpose: there is no real word to protect, so a false positive costs one
nonsense string swapped for another, and fragments too short to use against a
real corpus (`ass`, `tit`) are fine here. It rejects about 1.4% of draws
together with the quality filter. Extend `_UNSAFE` if something slips through.

## The word lists

Five lists under `data/`, one word per line, sorted, ASCII-only. Keeping them
separate lets the generator mix them in whatever proportion reads well -- mostly
human names, with the occasional `Stroopwafel` for a smile.

| File | Words | What it is |
| --- | --- | --- |
| `names.txt` | 76,880 | Human given names from around the world |
| `pet_names.txt` | 1,250 | Pet names that are *not* also human given names — `Tortellini`, `Figgy`, `Widget`, `Sprinkles` |
| `nouns_en.txt` | 3,062 | English common nouns — `Huckleberry`, `Megaphone`, `Clabber` |
| `nouns_es.txt` | 1,427 | Spanish common nouns — `Aguacate`, `Girasol`, `Sonajero` |
| `nouns_nl.txt` | 3,072 | Dutch common nouns — `Stoofpot`, `Racefiets`, `Zadelrob` |

The noun lists are deliberately restricted to *concrete, picturable* things --
foods, drinks, musical instruments, clothes, furniture, vehicles, plants, and
species. Abstract nouns are not funny; `Wafel` and `Koboldhaai` are.

Every entry is normalised so it can be dropped straight into filenames, log
lines, and plot legends:

- diacritics folded to ASCII (`Tünde` → `Tunde`, `Martí` → `Marti`, `Søren` → `Soren`)
- single alphabetic token only -- no spaces, hyphens, or apostrophes, so
  `Mary-Jane`, `Su-jin`, and `O'Brien` are dropped rather than mangled
- 3 to 12 characters, at least one vowel
- capitalised consistently (`Mckenna`, not `McKenna`)
- deduplicated case-insensitively after folding

`data/manifest.json` records the totals, the source URLs, and the filters that
were in force for the current build.

## Sources

Every source is public domain, CC0, or permissively licensed with attribution
only. **Nothing here is share-alike**, so the lists can be embedded in a
closed-source application without triggering copyleft obligations — see
[Licensing](#licensing).

### Human given names

| Source | License | New names |
| --- | --- | --- |
| [Wikidata](https://www.wikidata.org/) given-name items (`P31` = male/female/unisex given name), read via [QLever](https://qlever.dev/) | CC0 | **74,639** — 1.3M Latin-script labels across 38 languages, the bulk of the breadth |
| [sigpwned/popular-names-by-country-dataset](https://github.com/sigpwned/popular-names-by-country-dataset) | CC0 | **178** — most popular given names in each of 106 countries, from national statistics offices |
| [US SSA baby names](https://github.com/hackerb9/ssa-baby-names) (mirror of [ssa.gov](https://www.ssa.gov/oact/babynames/limits.html)) | Public domain | **2,063** — names recorded ≥100 times in a single year since 1880 |

The second and third sources add little in raw count because Wikidata already
covers most of what they contain, but they are what guarantees that the *common*
names are present rather than only the long tail.

### Pet names

City pet-licence registers, counted server-side through Socrata's aggregation
API: [Seattle](https://data.seattle.gov/resource/jguv-t9rb.csv) (≥3 licences) and
[New York City dogs](https://data.cityofnewyork.us/resource/nu7n-tubp.csv) (≥25).
The occurrence floor is a quality gate — it drops typos and one-off joke names
while keeping names real people actually used.

Then every name that is *also* a human given name is removed. That is what
leaves the whimsy: without it the list is another 60% copy of Bella, Max, and
Charlie, and with it you get `Cranberry`, `Moonshine`, `Toffee`, and `Paddington`.

### Common nouns

Wikidata again (CC0), traversing `P279*` (subclass of) from a curated set of
classes: food, drink, musical instrument, clothing, furniture, vehicle, plant,
plus vernacular species names via `P31` taxon at species rank.

Three classes were tried and dropped after looking at what they actually return:
`toy` (Wikidata files sex toys under it), `container` (cluster bombs and other
munitions), and `tool` (technical instruments, little whimsy). `animal` was
dropped too — its subclass chains reach human social roles like `widow` and
`castrato` rather than animals, which is why species come from the taxon query
instead.

Two filters do the heavy lifting:

- **Lowercase initial.** Wikidata capitalises brands and proper nouns but not
  common nouns, so this drops `Vegemite`, `Altoids`, and `Marsala` while keeping
  `stroopwafel` and `paksoi`. Applying the length limits server-side matters too:
  for the species query it turns a 64 MB download into 14 kB.
- **Attested in the language.** Wikidata labels a regional food with its native
  name in *every* language, so the raw English list arrives full of words that
  are not English (`Yakimochi`, `Xeremia`, `Joelho` — Portuguese for knee) and the
  Spanish list full of words that are not Spanish (`Rohwurst`, `Nabemono`,
  `Ontbijtkoek`). Each language is intersected with a general wordlist for that
  language: [dwyl/english-words](https://github.com/dwyl/english-words)
  (Unlicense), [lorenbrichter/Words](https://github.com/lorenbrichter/Words)
  (CC0), and [OpenTaal](https://github.com/OpenTaal/opentaal-wordlist) (Revised
  BSD / CC BY 3.0), each used only as a build-time membership test.

That second filter trades recall for precision, and the cost is real: Dutch
builds compounds productively, so no fixed lexicon lists them all, and genuine
words like `Monniksgier` and `Fluitzwaan` are lost along with the foreign ones.
Guaranteeing that every entry really is a word in the language seemed worth more
than the extra few thousand entries — but it is a one-line change to drop the
filter if you would rather have the volume.

## Licensing

These lists are meant to be embeddable in a closed-source application, so
share-alike sources are avoided on purpose. Worth recording, because it shaped a
decision:

The obvious source for whimsical nouns across all three languages was the
[Open Multilingual Wordnet](https://github.com/omwn/omw-data), which is aligned
to WordNet synsets and would have let one semantic filter (`noun.animal`,
`noun.food`, `noun.plant`) serve every language. Its Spanish data is CC BY 3.0
and fine, but **Open Dutch WordNet is CC BY-SA 4.0** — share-alike, and not
something to embed in a closed product. Hence Wikidata (CC0) for the nouns
instead.

The one thing to check before shipping: pet registers contain trademarked and
fictional names, so `pet_names.txt` includes `Pikachu`, `Yoda`, `Bilbo`, and
`Ewok`. Harmless for internal detector names; your call if these ever appear in
published figures.

## Endpoint quirks

Worth knowing before touching the build:

- Wikidata is read through **QLever's** public endpoint rather than
  `query.wikidata.org`. Same CC0 data, but QLever answers the big query in ~10 s,
  where WDQS cannot answer it at all: WDQS caps queries at 60 s and, past the
  cap, truncates the response mid-stream with a Java stack trace appended to an
  HTTP 200 body — so a naive build silently caches a partial list. Sharded into
  15 sub-queries it took ~20 minutes, and during a service incident it fell back
  to 1 request/min with `Retry-After: 1000`.
- QLever reports its own query timeouts as a JSON body, also under HTTP 200.
- `ssa.gov` blocks scripted downloads (Akamai 403), hence the GitHub mirror.
- CSV must be negotiated with an `Accept` header; a `?format=csv` parameter is
  ignored and answered with SPARQL XML.

Because a bad response can look like a good one, every response is
integrity-checked before it is cached, and the bulk Wikidata download is checked
against a companion `COUNT(DISTINCT ?label)` query and rejected unless the row
count matches exactly.

## Excluded words

Names that would be awkward, offensive, or read as a statement when printed on a
plot or in a paper are excluded:

- deities and divine names (`Jesus`, `Allah`, `Buddha`, `Satan`)
- prophets and figures whose names are widely treated as sacred, including the
  many romanisations of `Muhammad`
- dictators, mass murderers, and notorious historical figures (`Adolf`,
  `Stalin`, `Saddam`, `Mengele`)
- political and religious movements (`Nazi`, `Isis`, `Jihad`)
- slurs, profanity, crude terms, drugs, weapons
- genuine names elsewhere that an English reader misreads as crude (`Dick`,
  `Fanny`, `Willy`, `Snot`, and `Niggi`/`Niggl`, Swiss German diminutives of
  Nikolaus)
- words that are not offensive, just not whimsical — weapons of war, death,
  disease, and drugs, in any of the three languages (`Missile`, `Bommenwerper`,
  `Doodskist`, `Hearse`, `Cancer`, `Cannabis`)

The lists live in [`tools/blocklist.txt`](tools/blocklist.txt) (exact matches)
and [`tools/blockpatterns.txt`](tools/blockpatterns.txt) (regexes for spelling
families). Both are commented by category and are meant to be edited.

Names that are merely *religious in origin* are deliberately kept -- `Maria`,
`Christopher`, `Ali`, `Ibrahim`, `Krishna`, and `Omar` are ordinary, extremely
common names, and excluding them would gut the corpus without making anyone
safer. A few judgement calls sit between the two policies and are noted inline
in the blocklist; the notable ones:

- `Jesus` is excluded, which also removes the Spanish `Jesús`. This is a common
  Hispanic given name; it is excluded anyway because English-language readers
  will read it as the religious figure.
- The `^adolf`/`^adolph` patterns also remove the ordinary Spanish and French
  names `Adolfo` and `Adolphe`.
- `Benito`, `Franco`, `Amin`, `Idi`, and `Mao` are excluded for their historical
  associations even though each is an ordinary name somewhere.
- `Attila` and `Vladimir` are kept: both are everyday given names (Hungarian and
  Slavic respectively) and the association is much weaker.
- `Randy`, `Gay`, and `Dong` are kept where `Dick` and `Fanny` are not: all read
  as names first, and `Dong` is a common Vietnamese and Korean name.
- Substring matching is used sparingly, since it is what breaks legitimate
  names
- `Tank`, `Submarine`, `Onderzeeboot`, and `Raket` survive the weapons rule: a
  submarine is a machine rather than a weapon, `Tank` is one of the most common
  affectionate dog names in the NYC register, and Dutch `raket` is a rocket, a
  tennis racket, *and* arugula.
- `Puto` was removed even though it arrived as the name of a Filipino rice cake,
  because it is a slur in Spanish. `Negra` went for the same kind of reason.

To review exactly what the filter removed, per list:

```bash
python tools/build_names.py --show-excluded
```

## Rebuilding

```bash
python tools/build_names.py
```

Standard library only, no dependencies; a cold build takes about 30 seconds.
Downloads are cached under `build_cache/` (git-ignored, ~11 MB), so re-runs after
the first are fully offline. Use `--refresh` to re-download every source. The
lists are written into `resonator_name_generator/data/` so they ship with the
package.

