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
"""

from __future__ import annotations

import random
from functools import lru_cache
from importlib.resources import files
from typing import Iterable, Mapping, Sequence

__all__ = [
    "CATEGORIES",
    "DEFAULT_WEIGHTS",
    "random_name",
    "random_names",
    "words",
]

#: The available word lists. Each is a file ``data/<category>.txt``.
CATEGORIES = ("names", "pet_names", "nouns_en", "nouns_es", "nouns_nl")

#: Mostly people, with roughly one draw in five being something sillier. Tuned so
#: a plot of a few dozen resonators reads as a list of names with the occasional
#: Stroopwafel, rather than as a joke.
DEFAULT_WEIGHTS = {
    "names": 8.0,
    "pet_names": 1.0,
    "nouns_en": 0.4,
    "nouns_es": 0.3,
    "nouns_nl": 0.3,
}


@lru_cache(maxsize=None)
def words(category: str) -> tuple[str, ...]:
    """Return every word in ``category``, loaded on first use and then cached."""
    if category not in CATEGORIES:
        raise ValueError(
            f"unknown category {category!r}; choose from {', '.join(CATEGORIES)}"
        )
    text = (files(__package__) / "data" / f"{category}.txt").read_text(encoding="utf-8")
    return tuple(text.split())


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


def _pick(live: Mapping[str, float], rng: random.Random) -> str:
    categories = list(live)
    return rng.choices(categories, weights=[live[c] for c in categories])[0]


def random_name(
    weights: Mapping[str, float] | None = None,
    *,
    rng: random.Random | int | None = None,
) -> str:
    """Return one random name.

    :param weights: relative likelihood per category, e.g.
        ``{"names": 8, "pet_names": 1}``. Categories omitted from the mapping are
        never drawn. Defaults to :data:`DEFAULT_WEIGHTS`.
    :param rng: a :class:`random.Random`, or an int seed, for reproducible draws.
    """
    resolved = _resolve_rng(rng)
    return resolved.choice(words(_pick(_resolve_weights(weights), resolved)))


def random_names(
    n: int,
    weights: Mapping[str, float] | None = None,
    *,
    unique: bool = True,
    rng: random.Random | int | None = None,
    avoid: Iterable[str] = (),
) -> list[str]:
    """Return ``n`` random names, distinct from each other by default.

    Naming an array of resonators is the normal case, and two detectors with the
    same name are worse than no names at all -- hence ``unique=True``.

    :param n: how many names to return.
    :param weights: as for :func:`random_name`.
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
    live = _resolve_weights(weights)
    if not unique:
        return [resolved.choice(words(_pick(live, resolved))) for _ in range(n)]

    # Shuffling each pool once and popping from the end draws without replacement
    # in O(1) per name, and stays correct as a pool empties -- which retrying on
    # collisions does not, once a pool is nearly exhausted.
    pools = {category: list(words(category)) for category in live}
    for pool in pools.values():
        resolved.shuffle(pool)

    seen = {name for name in avoid}
    drawn: list[str] = []
    while len(drawn) < n:
        if not live:
            available = len(drawn)
            raise ValueError(
                f"asked for {n} distinct names but only {available} were available "
                f"from {', '.join(sorted(pools))}"
            )
        category = _pick(live, resolved)
        pool = pools[category]
        picked = None
        while pool and picked is None:
            candidate = pool.pop()
            # A word can appear in two lists (a noun that is also a pet name), so
            # uniqueness is checked across categories, not within one.
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
    args = parser.parse_args(argv)

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
            args.n, weights, unique=not args.repeats_ok, rng=args.seed
        ):
            print(name)
    except ValueError as exc:
        parser.error(str(exc))
    return 0
