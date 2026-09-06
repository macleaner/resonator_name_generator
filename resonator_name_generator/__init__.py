"""Random, memorable names for detectors.

    >>> from resonator_name_generator import random_name, random_names
    >>> random_name()                                    # doctest: +SKIP
    'Rosalind'
    >>> random_names(4, {"names": 4, "nouns_nl": 1})      # doctest: +SKIP
    ['Ilinca', 'Stroopwafel', 'Aurangzeb', 'Marnie']

One category is made up rather than looked up -- ``syllabic_strings`` invents
pronounceable words that are nobody's name -- and any draw can be held to a
length, which applies to the real words and the invented ones alike:

    >>> random_names(3, {"names": 3, "syllabic_strings": 1}, length=6)  # doctest: +SKIP
    ['Marnie', 'Tavren', 'Zonira']

When a memorable name is the wrong answer, ``boring`` mode just counts:

    >>> from resonator_name_generator import boring_names
    >>> boring_names(3)
    ['R0001', 'R0002', 'R0003']
    >>> boring_names(3, "kid")
    ['kid0001', 'kid0002', 'kid0003']

See :mod:`resonator_name_generator.generator` for how the category weighting
works, :mod:`resonator_name_generator.syllables` for how a syllabic string is
put together, and :mod:`resonator_name_generator.boring` for the numbering.
"""

from .boring import (
    DEFAULT_PREFIX,
    DEFAULT_WIDTH,
    boring_name,
    boring_names,
)
from .generator import (
    CATEGORIES,
    DEFAULT_SYLLABIC_LENGTH,
    DEFAULT_WEIGHTS,
    SYLLABIC_STRINGS,
    WORD_LISTS,
    random_name,
    random_names,
    words,
)
from .syllables import (
    MIN_LENGTH,
    random_syllabic_string,
)

__all__ = [
    "CATEGORIES",
    "DEFAULT_PREFIX",
    "DEFAULT_SYLLABIC_LENGTH",
    "DEFAULT_WEIGHTS",
    "DEFAULT_WIDTH",
    "MIN_LENGTH",
    "SYLLABIC_STRINGS",
    "WORD_LISTS",
    "boring_name",
    "boring_names",
    "random_name",
    "random_names",
    "random_syllabic_string",
    "words",
]

__version__ = "0.1.0"
