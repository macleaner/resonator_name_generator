"""Draw random, memorable names for detectors.

The word lists in ``data/`` are kept separate by category so that the mix is
configurable. Every draw picks a *category* first, by weight, and then a word
uniformly from within it::

    >>> random_name()                                   # doctest: +SKIP
    'Rosalind'
    >>> random_name({"nouns_nl": 1})                    # doctest: +SKIP
    'Stroopwafel'
    >>> random_names(3, {"names": 4, "pet_names": 1})    # doctest: +SKIP
    ['Ilinca', 'Tortellini', 'Aurangzeb']

Weighting by category rather than by word is the point: ``names.txt`` is roughly
25x the size of the other four lists put together, so drawing uniformly from
their union would yield about 90% human names whatever you did. Weights are
relative, so ``{"names": 8, "pet_names": 2}`` and ``{"names": 4, "pet_names": 1}``
mean the same thing, and a category left out of the dict is not drawn from at
all.

One category, ``gibberish``, is not a list but a generator: it makes up
pronounceable words that are nobody's name, and it is off by default. Weight it
to salt the real words with invented ones::

    >>> random_names(4, {"names": 3, "gibberish": 1})    # doctest: +SKIP
    ['Ilinca', 'Tavren', 'Aurangzeb', 'Socliepa']

Every draw can also be held to a length, which applies to the whole mix -- the
lists are filtered to the words that fit and the gibberish is generated to
match, so the result is uniform in width whichever category each name came
from::

    >>> random_names(3, length=6)                        # doctest: +SKIP
    ['Marnie', 'Kettle', 'Zonira']
    >>> random_names(3, length=(4, 6))                   # doctest: +SKIP
    ['Ilse', 'Marnie', 'Wafel']

See :mod:`resonator_name_generator.syllables` for how the gibberish is built,
and :mod:`resonator_name_generator.boring` for when a name is not wanted at all
and a numbered ``R0001`` will do.
"""

from __future__ import annotations

import random
from functools import lru_cache
from importlib.resources import files
from typing import Iterable, Mapping, Sequence

from .boring import DEFAULT_PREFIX, DEFAULT_WIDTH, boring_names
from .syllables import MIN_LENGTH, random_gibberish

__all__ = [
    "CATEGORIES",
    "DEFAULT_GIBBERISH_LENGTH",
    "DEFAULT_WEIGHTS",
    "GIBBERISH",
    "WORD_LISTS",
    "random_name",
    "random_names",
    "words",
]

#: The category that is generated rather than looked up.
GIBBERISH = "gibberish"

#: The file-backed categories. Each is a file ``data/<category>.txt``.
WORD_LISTS = ("names", "pet_names", "nouns_en", "nouns_es", "nouns_nl")

#: Everything that can carry a weight.
CATEGORIES = (*WORD_LISTS, GIBBERISH)

#: Mostly people, with roughly one draw in five being something sillier. Tuned so
#: a plot of a few dozen resonators reads as a list of names with the occasional
#: Stroopwafel, rather than as a joke.
#:
#: ``gibberish`` sits here at zero rather than being left out: the default mix is
#: real words, and invented ones are something to opt into, but a weight of zero
#: is a more discoverable way to say so than an absence.
DEFAULT_WEIGHTS = {
    "names": 8.0,
    "pet_names": 1.0,
    "nouns_en": 0.4,
    "nouns_es": 0.3,
    "nouns_nl": 0.3,
    "gibberish": 0.0,
}

#: How long gibberish is when no length was asked for. The real lists put about
#: 90% of their words in this range, so unconstrained gibberish blends in rather
#: than standing out as the long entry in every legend.
DEFAULT_GIBBERISH_LENGTH = (4, 9)


def words(
    category: str, length: int | tuple[int, int] | None = None
) -> tuple[str, ...]:
    """Return the words in ``category``, loaded on first use and then cached.

    :param category: one of :data:`WORD_LISTS`. ``gibberish`` is generated, not
        stored, so it has no word list to return.
    :param length: an exact length, or a ``(min, max)`` pair, to return only the
        words that fit. ``None`` returns the whole list.
    """
    return _words(category, _resolve_length(length))


@lru_cache(maxsize=None)
def _words(category: str, bounds: tuple[int, int] | None) -> tuple[str, ...]:
    # Cached on the *normalised* bounds so that 6 and (6, 6) share an entry.
    if category == GIBBERISH:
        raise ValueError(
            f"{GIBBERISH!r} is generated rather than stored and has no word "
            f"list; call random_gibberish() for one word of it"
        )
    if category not in WORD_LISTS:
        raise ValueError(
            f"unknown category {category!r}; choose from {', '.join(CATEGORIES)}"
        )
    text = (files(__package__) / "data" / f"{category}.txt").read_text(encoding="utf-8")
    everything = tuple(text.split())
    if bounds is None:
        return everything
    low, high = bounds
    return tuple(word for word in everything if low <= len(word) <= high)


def _resolve_length(
    length: int | tuple[int, int] | None,
) -> tuple[int, int] | None:
    """Normalise a length, an inclusive ``(min, max)`` pair, or nothing."""
    if length is None:
        return None
    if isinstance(length, int):
        low = high = length
    else:
        low, high = (int(bound) for bound in length)
    if low < 1:
        raise ValueError(f"length must be positive, got {low}")
    if high < low:
        raise ValueError(f"length range is empty: {low} to {high}")
    return low, high


def _resolve_rng(rng: random.Random | int | None) -> random.Random:
    """Accept a Random, a seed, or nothing.

    Passing a seed is the easy way to make a run reproducible: the same seed and
    the same weights give the same names in the same order.
    """
    if rng is None:
        return random.Random()
    if isinstance(rng, random.Random):
        return rng
    return random.Random(rng)


def _resolve_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    """Validate ``weights`` and drop the categories that cannot be drawn."""
    if weights is None:
        weights = DEFAULT_WEIGHTS

    unknown = sorted(set(weights) - set(CATEGORIES))
    if unknown:
        raise ValueError(
            f"unknown categor{'y' if len(unknown) == 1 else 'ies'} "
            f"{', '.join(repr(u) for u in unknown)}; "
            f"choose from {', '.join(CATEGORIES)}"
        )
    negative = sorted(name for name, weight in weights.items() if weight < 0)
    if negative:
        raise ValueError(f"negative weight for {', '.join(negative)}")

    live = {name: float(weight) for name, weight in weights.items() if weight > 0}
    if not live:
        raise ValueError("at least one category needs a weight above zero")
    return live


def _drawable(
    live: dict[str, float], bounds: tuple[int, int] | None
) -> dict[str, float]:
    """Drop the weighted categories that hold nothing of the required length.

    A length that suits human names need not suit Dutch compounds, so rather
    than fail on whichever category the first draw happened to land in, the ones
    that cannot answer are removed up front and their weight passes to the rest.
    """
    if bounds is None:
        return live
    low, high = bounds
    able: dict[str, float] = {}
    for category, weight in live.items():
        if category == GIBBERISH:
            # Nothing shorter than a syllable can be built, but anything longer
            # can, so gibberish only drops out of a range below MIN_LENGTH.
            if high >= MIN_LENGTH:
                able[category] = weight
        elif words(category, bounds):
            able[category] = weight
    if not able:
        span = f"{low}" if low == high else f"{low} to {high}"
        raise ValueError(
            f"nothing of length {span} in {', '.join(sorted(live))}"
        )
    return able


def _pick(live: Mapping[str, float], rng: random.Random) -> str:
    categories = list(live)
    return rng.choices(categories, weights=[live[c] for c in categories])[0]


def _gibberish_length(bounds: tuple[int, int] | None, rng: random.Random) -> int:
    low, high = bounds if bounds is not None else DEFAULT_GIBBERISH_LENGTH
    return rng.randint(max(low, MIN_LENGTH), high)


def _draw(category: str, bounds: tuple[int, int] | None, rng: random.Random) -> str:
    if category == GIBBERISH:
        return random_gibberish(_gibberish_length(bounds, rng), rng=rng)
    return rng.choice(words(category, bounds))


def random_name(
    weights: Mapping[str, float] | None = None,
    *,
    length: int | tuple[int, int] | None = None,
    rng: random.Random | int | None = None,
) -> str:
    """Return one random name.

    :param weights: relative likelihood per category, e.g.
        ``{"names": 8, "pet_names": 1}``. Categories omitted from the mapping are
        never drawn. Defaults to :data:`DEFAULT_WEIGHTS`.
    :param length: an exact length, or an inclusive ``(min, max)`` pair, that the
        name must fit. Applies to every category: the lists are filtered and the
        gibberish is generated to match.
    :param rng: a :class:`random.Random`, or an int seed, for reproducible draws.
    :raises ValueError: if no weighted category holds a word of that length.
    """
    resolved = _resolve_rng(rng)
    bounds = _resolve_length(length)
    live = _drawable(_resolve_weights(weights), bounds)
    return _draw(_pick(live, resolved), bounds, resolved)


#: Consecutive gibberish words that all turn out to be duplicates before the
#: category is treated as exhausted. There is no pool to watch empty, so this
#: stands in for one; a run this long means the space for that length really is
#: used up rather than merely unlucky, and it can only be paid once because the
#: category is dropped afterwards.
_GIBBERISH_MISSES = 5000


def random_names(
    n: int,
    weights: Mapping[str, float] | None = None,
    *,
    length: int | tuple[int, int] | None = None,
    unique: bool = True,
    rng: random.Random | int | None = None,
    avoid: Iterable[str] = (),
) -> list[str]:
    """Return ``n`` random names, distinct from each other by default.

    Naming an array of resonators is the normal case, and two detectors with the
    same name are worse than no names at all -- hence ``unique=True``.

    :param n: how many names to return.
    :param weights: as for :func:`random_name`.
    :param length: as for :func:`random_name`. Worth pairing with a weighted
        ``gibberish``: a length narrow enough to make a legend line up is often
        narrow enough to drain the lists, and gibberish does not run out.
    :param unique: when true, no name is repeated and none is drawn from
        ``avoid``. A category that runs out is dropped and the remaining weights
        carry on between them, so asking for more names than one small list holds
        still works as long as the others can cover it.
    :param rng: a :class:`random.Random`, or an int seed, for reproducible draws.
    :param avoid: names already in use, e.g. those of resonators already named.
    :raises ValueError: if ``unique`` is set and the weighted categories cannot
        supply ``n`` distinct names.
    """
    if n < 0:
        raise ValueError(f"n must not be negative, got {n}")
    resolved = _resolve_rng(rng)
    bounds = _resolve_length(length)
    live = _drawable(_resolve_weights(weights), bounds)
    if not unique:
        return [_draw(_pick(live, resolved), bounds, resolved) for _ in range(n)]

    # Shuffling each pool once and popping from the end draws without replacement
    # in O(1) per name, and stays correct as a pool empties -- which retrying on
    # collisions does not, once a pool is nearly exhausted. Gibberish has no pool
    # to shuffle and is handled by rejection below, but it reaches the same end:
    # a category that cannot produce anything new is dropped, and the remaining
    # weights carry on between them.
    weighted = ", ".join(sorted(live))
    pools = {
        category: list(words(category, bounds))
        for category in live
        if category != GIBBERISH
    }
    for pool in pools.values():
        resolved.shuffle(pool)

    seen = {name for name in avoid}
    drawn: list[str] = []
    while len(drawn) < n:
        if not live:
            available = len(drawn)
            raise ValueError(
                f"asked for {n} distinct names but only {available} were available "
                f"from {weighted}"
            )
        category = _pick(live, resolved)
        picked = None
        if category == GIBBERISH:
            for _ in range(_GIBBERISH_MISSES):
                candidate = random_gibberish(
                    _gibberish_length(bounds, resolved), rng=resolved
                )
                if candidate not in seen:
                    picked = candidate
                    break
        else:
            pool = pools[category]
            while pool and picked is None:
                candidate = pool.pop()
                # A word can appear in two lists (a noun that is also a pet
                # name), so uniqueness is checked across categories, not within
                # one -- and gibberish is checked against the real words too, so
                # an invented name never collides with a drawn one.
                if candidate not in seen:
                    picked = candidate
        if picked is None:
            del live[category]
            continue
        seen.add(picked)
        drawn.append(picked)
    return drawn


def _main(argv: Sequence[str] | None = None) -> int:
    """``python -m resonator_name_generator`` -- print a few names to eyeball."""
    import argparse

    parser = argparse.ArgumentParser(description="Draw random resonator names.")
    parser.add_argument("-n", type=int, default=10, help="how many names (default 10)")
    parser.add_argument("--seed", type=int, help="seed, for a reproducible draw")
    parser.add_argument(
        "-w",
        "--weight",
        action="append",
        default=[],
        metavar="CATEGORY=WEIGHT",
        help="override one category's weight; repeatable",
    )
    parser.add_argument(
        "--repeats-ok",
        action="store_true",
        help="allow the same name more than once",
    )
    parser.add_argument(
        "--length",
        metavar="N|MIN-MAX",
        help="hold every name to N characters, or to the range MIN-MAX",
    )
    parser.add_argument(
        "--boring",
        nargs="?",
        const=DEFAULT_PREFIX,
        metavar="PREFIX",
        help=(
            f"number them instead: {DEFAULT_PREFIX}0001, {DEFAULT_PREFIX}0002, "
            f"... (PREFIX defaults to {DEFAULT_PREFIX!r})"
        ),
    )
    args = parser.parse_args(argv)

    length: int | tuple[int, int] | None = None
    if args.length:
        low, dash, high = args.length.partition("-")
        try:
            length = (int(low), int(high)) if dash else int(low)
        except ValueError:
            parser.error(f"expected N or MIN-MAX, got {args.length!r}")

    if args.boring is not None:
        # Numbering is not a draw, so the knobs that shape one do not apply --
        # better to say so than to accept them and quietly do nothing.
        if args.weight:
            parser.error("--boring draws from no category, so weights do nothing")
        if args.repeats_ok:
            parser.error("--boring names are numbered and so never repeat")
        width = DEFAULT_WIDTH
        if length is not None:
            if not isinstance(length, int):
                parser.error("--boring needs an exact --length, not a range")
            width = length - len(args.boring)
            if width < 1:
                parser.error(
                    f"--length {length} leaves no room for a counter after "
                    f"{args.boring!r}"
                )
            if len(str(args.n)) > width:
                parser.error(
                    f"--length {length} fits {10 ** width - 1} names after "
                    f"{args.boring!r}, not {args.n}"
                )
        try:
            for name in boring_names(args.n, args.boring, width=width):
                print(name)
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    weights: dict[str, float] | None = None
    if args.weight:
        weights = {}
        for item in args.weight:
            category, _, value = item.partition("=")
            if not value:
                parser.error(f"expected CATEGORY=WEIGHT, got {item!r}")
            try:
                weights[category] = float(value)
            except ValueError:
                parser.error(f"weight for {category!r} is not a number: {value!r}")

    try:
        for name in random_names(
            args.n,
            weights,
            length=length,
            unique=not args.repeats_ok,
            rng=args.seed,
        ):
            print(name)
    except ValueError as exc:
        parser.error(str(exc))
    return 0
