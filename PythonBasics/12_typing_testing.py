"""12 - Typing, testing, modules/packaging basics and code quality.

Run: python 12_typing_testing.py          (runs its own unittest tests)
For pytest style see the notes at the bottom.
"""
import unittest
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterator, Optional, Protocol, TypedDict, TypeVar, Union

T = TypeVar("T")                                    # a placeholder type for generic functions


class Status(Enum):
    """Enum: a fixed set of named constants (better than magic strings)."""
    ONLINE = "online"
    OFFLINE = "offline"


class DeviceRecord(TypedDict):
    """Typed dictionary: documents the keys of a dict (e.g. parsed JSON). Checked by mypy, not at runtime."""
    id: str
    status: str


class HasArea(Protocol):
    """Protocol: structural typing. Anything with an area() method qualifies (duck typing, checked by mypy)."""

    def area(self) -> float:
        """Any class providing this method matches the protocol; no inheritance needed."""
        ...


@dataclass(frozen=True)                             # frozen = immutable and hashable
class Reading:
    """A single sensor reading."""
    device: str
    value: float
    unit: str = "C"


def first(items: list[T], default: Optional[T] = None) -> Optional[T]:
    """Generic function: return the first item, or the default if the list is empty.

    T means "whatever type the list holds"; the result has the same type.
    """
    return items[0] if items else default


def parse_id(raw: Union[int, str]) -> int:          # Union[int, str] is the same as int | str on 3.10+
    """Convert an id given as int or str into an int."""
    return int(raw)


def apply(fn: Callable[[int], int], xs: list[int]) -> Iterator[int]:
    """Lazily apply fn to every item. Callable[[int], int] = a function taking an int and returning an int."""
    for x in xs:
        yield fn(x)


def average(values: list[float]) -> float:
    """Mean of the values; raises ValueError for an empty list. This is the function under test."""
    if not values:
        raise ValueError("empty")
    return sum(values) / len(values)


class TestAverage(unittest.TestCase):
    """unittest test case: every method starting with test_ is run as a separate test."""

    def setUp(self):                                # runs before EACH test
        """Prepare fresh data for every test."""
        self.data = [1.0, 2.0, 3.0]

    def test_basic(self):
        """Normal case: the mean of 1, 2, 3 is 2."""
        self.assertEqual(average(self.data), 2.0)

    def test_empty_raises(self):
        """Error case: an empty list must raise ValueError."""
        with self.assertRaises(ValueError):
            average([])

    def test_float_close(self):
        """Compare floats with assertAlmostEqual, never with ==."""
        self.assertAlmostEqual(average([0.1, 0.2]), 0.15)

    def test_helpers(self):
        """Check the small helper functions, the Enum and the frozen dataclass."""
        self.assertEqual(first([]), None)
        self.assertEqual(first([5]), 5)
        self.assertEqual(parse_id("7"), 7)
        self.assertEqual(list(apply(lambda x: x + 1, [1, 2])), [2, 3])
        self.assertEqual(Status("online"), Status.ONLINE)           # look up an enum member by value
        self.assertEqual(Reading("a", 1.0), Reading("a", 1.0))      # dataclasses compare by fields
        with self.assertRaises(Exception):                          # frozen dataclass cannot be changed
            Reading("a", 1.0).value = 2.0

    def test_mock(self):
        """Mocks replace real collaborators (network, database) so tests are fast and isolated."""
        from unittest.mock import MagicMock, patch
        api = MagicMock()                                           # fake object that records how it was used
        api.get_status.return_value = "online"                      # program its answer
        self.assertEqual(api.get_status("gw1"), "online")
        api.get_status.assert_called_once_with("gw1")               # verify it was called exactly like this
        with patch("builtins.input", return_value="yes"):           # temporarily replace input() with a fake
            self.assertEqual(input("ok? "), "yes")


if __name__ == "__main__":
    unittest.main(verbosity=1)                      # discover and run the tests in this file

# --- Notes ---
# pytest equivalents (pip install pytest; run `pytest`):
#     def test_basic(): assert average([1, 2, 3]) == 2
#     def test_empty():
#         with pytest.raises(ValueError): average([])
#     @pytest.mark.parametrize("xs,exp", [([1, 1], 1), ([1, 3], 2)])   # many cases, one test
#     @pytest.fixture                                                   # reusable setup
#
# Modules and packaging:
#   - A module is a .py file; a package is a folder with __init__.py. `from pkg.mod import name`.
#   - `if __name__ == "__main__":` runs code only when the file is executed, not when imported.
#   - Virtual environments isolate dependencies:  python -m venv .venv ; pip install -r requirements.txt
#   - Quality tools: black (format), ruff/flake8 (lint), mypy (types), pytest (tests), pre-commit (hooks).
