"""Random, memorable names for detectors.

    >>> from resonator_name_generator import random_name, random_names
    >>> random_name()                                    # doctest: +SKIP
    'Rosalind'
    >>> random_names(4, {"names": 4, "nouns_nl": 1})      # doctest: +SKIP
    ['Ilinca', 'Stroopwafel', 'Aurangzeb', 'Marnie']

One category is made up rather than looked up -- ``gibberish`` invents
pronounceable words that are nobody's name -- and any draw can be held to a
length, which applies to the real words and the invented ones alike:

    >>> random_names(3, {"names": 3, "gibberish": 1}, length=6)  # doctest: +SKIP
    ['Marnie', 'Tavren', 'Zonira']

See :mod:`resonator_name_generator.generator` for how the category weighting
works, and :mod:`resonator_name_generator.syllables` for how the gibberish is
put together.
"""

from .generator import (
    CATEGORIES,
    DEFAULT_GIBBERISH_LENGTH,
    DEFAULT_WEIGHTS,
    GIBBERISH,
    WORD_LISTS,
    random_name,
    random_names,
    words,
)
from .syllables import (
    MIN_LENGTH,
    random_gibberish,
)

__all__ = [
    "CATEGORIES",
    "DEFAULT_GIBBERISH_LENGTH",
    "DEFAULT_WEIGHTS",
    "GIBBERISH",
    "MIN_LENGTH",
    "WORD_LISTS",
    "random_gibberish",
    "random_name",
    "random_names",
    "words",
]

__version__ = "0.1.0"
