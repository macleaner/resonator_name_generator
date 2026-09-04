"""Random, memorable names for detectors.

    >>> from resonator_name_generator import random_name, random_names
    >>> random_name()                                    # doctest: +SKIP
    'Rosalind'
    >>> random_names(4, {"names": 4, "nouns_nl": 1})      # doctest: +SKIP
    ['Ilinca', 'Stroopwafel', 'Aurangzeb', 'Marnie']

Or coin pronounceable words of an exact length instead of drawing real ones:

    >>> from resonator_name_generator import random_string, random_strings
    >>> random_strings(3, 6)                              # doctest: +SKIP
    ['Tavren', 'Meliza', 'Sondik']

See :mod:`resonator_name_generator.generator` for how the category weighting
works, and :mod:`resonator_name_generator.syllables` for how the coined words
are put together.
"""

from .generator import (
    CATEGORIES,
    DEFAULT_WEIGHTS,
    random_name,
    random_names,
    words,
)
from .syllables import (
    MIN_LENGTH,
    random_string,
    random_strings,
)

__all__ = [
    "CATEGORIES",
    "DEFAULT_WEIGHTS",
    "MIN_LENGTH",
    "random_name",
    "random_names",
    "random_string",
    "random_strings",
    "words",
]

__version__ = "0.1.0"
