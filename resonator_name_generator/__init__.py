"""Random, memorable names for detectors.

    >>> from resonator_name_generator import random_name, random_names
    >>> random_name()                                    # doctest: +SKIP
    'Rosalind'
    >>> random_names(4, {"names": 4, "nouns_nl": 1})      # doctest: +SKIP
    ['Ilinca', 'Stroopwafel', 'Aurangzeb', 'Marnie']

See :mod:`resonator_name_generator.generator` for how the category weighting
works.
"""

from .generator import (
    CATEGORIES,
    DEFAULT_WEIGHTS,
    random_name,
    random_names,
    words,
)

__all__ = [
    "CATEGORIES",
    "DEFAULT_WEIGHTS",
    "random_name",
    "random_names",
    "words",
]

__version__ = "0.1.0"
