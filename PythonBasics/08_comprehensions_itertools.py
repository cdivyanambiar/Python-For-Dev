"""08 - Comprehensions, itertools, sorting, slicing and other everyday idioms.

Run: python 08_comprehensions_itertools.py
Each function demonstrates one topic and checks itself with assert.
"""
import itertools
import operator
from collections import Counter


def comprehensions():
    """List, set and dict comprehensions, nested loops and flattening."""
    nums = range(6)
    assert [x * x for x in nums if x % 2 == 0] == [0, 4, 16]             # list: [expression for x in items if condition]
    assert {x % 3 for x in nums} == {0, 1, 2}                            # set: unique results
    assert {x: x * x for x in range(3)} == {0: 0, 1: 1, 2: 4}            # dict: key: value
    assert [(x, y) for x in range(2) for y in "ab"] == [(0, "a"), (0, "b"), (1, "a"), (1, "b")]   # nested loops, left to right
    assert [x if x > 1 else 0 for x in range(4)] == [0, 0, 2, 3]         # if/else goes BEFORE the for; a filter goes AFTER
    assert [c for row in [[1, 2], [3]] for c in row] == [1, 2, 3]        # flatten a list of lists


def unpacking_and_swapping():
    """Tuple unpacking, star-unpacking, swapping and enumerate."""
    a, b = 1, 2
    a, b = b, a                                                          # swap without a temporary variable
    first, *middle, last = [1, 2, 3, 4]                                  # *middle takes everything in between
    assert (a, b, first, middle, last) == (2, 1, 1, [2, 3], 4)
    assert [*"ab", *[1]] == ["a", "b", 1] and {**{"x": 1}, **{"y": 2}} == {"x": 1, "y": 2}   # merge sequences and dicts
    for i, (k, v) in enumerate({"a": 1}.items()):                        # index plus a (key, value) pair
        assert (i, k, v) == (0, "a", 1)


def itertools_tour():
    """The itertools functions worth knowing."""
    assert list(itertools.chain([1], [2, 3])) == [1, 2, 3]               # join iterables end to end
    assert list(itertools.islice(itertools.count(10, 5), 3)) == [10, 15, 20]   # first 3 of an infinite counter
    assert list(itertools.accumulate([1, 2, 3, 4])) == [1, 3, 6, 10]     # running totals
    assert list(itertools.combinations("abc", 2)) == [("a", "b"), ("a", "c"), ("b", "c")]   # order does not matter
    assert list(itertools.permutations([1, 2])) == [(1, 2), (2, 1)]      # order matters
    assert list(itertools.product("ab", [0, 1])) == [("a", 0), ("a", 1), ("b", 0), ("b", 1)]   # cartesian product
    data = sorted([("a", 1), ("b", 1), ("c", 2)], key=operator.itemgetter(1))   # groupby needs the data sorted by the same key
    grouped = {k: [x[0] for x in g] for k, g in itertools.groupby(data, key=operator.itemgetter(1))}
    assert grouped == {1: ["a", "b"], 2: ["c"]}
    assert list(itertools.zip_longest([1, 2], [9], fillvalue=0)) == [(1, 9), (2, 0)]   # pad the shorter input
    pairs = list(itertools.pairwise([1, 4, 9]))                          # consecutive pairs (3.10+)
    assert pairs == [(1, 4), (4, 9)] and [b - a for a, b in pairs] == [3, 5]   # differences between neighbours


def sorting_and_slicing():
    """sorted vs sort, keys, stability and slicing tricks."""
    words = ["bb", "a", "ccc"]
    assert sorted(words, key=len) == ["a", "bb", "ccc"] and words == ["bb", "a", "ccc"]   # sorted() returns a copy
    words.sort(key=len, reverse=True)                                    # .sort() changes the list in place
    assert words == ["ccc", "bb", "a"]
    s = [0, 1, 2, 3, 4, 5]
    assert s[-2:] == [4, 5] and s[::2] == [0, 2, 4] and s[::-1][0] == 5 and s[10:] == []   # slices never raise IndexError
    rows = [{"n": "x", "v": 2}, {"n": "y", "v": 1}]
    assert sorted(rows, key=operator.itemgetter("v"))[0]["n"] == "y"     # itemgetter is a faster alternative to a lambda
    assert sorted([3, 1, 2], reverse=True) == [3, 2, 1]                  # sort is stable: equal keys keep their order


def truthiness_and_comparison():
    """What counts as true/false, `is` vs `==`, `and`/`or` return values, and number operators."""
    assert not [] and not "" and not 0 and not None and not {}          # falsy values
    assert [1] and "a" and -1                                            # everything else is truthy
    assert 1 < 2 < 3 and (1 == 1.0) and ("a" < "b")                      # chained comparisons
    x = None
    assert x is None                                                     # use `is` for None/True/False
    assert (x or "default") == "default" and (0 or []) == []             # `or` returns the first truthy value (or the last)
    assert (1 and 2) == 2 and (0 and 2) == 0                             # `and` returns the first falsy value (or the last)
    assert int("7") + float("1.5") == 8.5 and 7 // 2 == 3 and 7 % 2 == 1 and 2 ** 10 == 1024 and -7 // 2 == -4   # // floors toward minus infinity


def walrus_and_match():
    """Assignment expressions (:=) and structural pattern matching (match/case)."""
    data = [1, 2, 3, 4]
    if (n := len(data)) > 3:                                             # assign and test in one expression (3.8+)
        assert n == 4

    def kind(cmd):                                                       # structural pattern matching (3.10+)
        """Classify a command by its shape."""
        match cmd:
            case {"op": "add", "args": [a, b]}:                          # dict with these keys, args has exactly two items
                return a + b
            case ["quit"] | ["exit"]:                                    # either pattern
                return "bye"
            case int() | float():                                        # by type
                return "number"
            case _:                                                      # default
                return "unknown"
    assert kind({"op": "add", "args": [1, 2]}) == 3 and kind(["exit"]) == "bye" and kind(2.5) == "number"


def useful_one_liners():
    """Short idioms that show up constantly in interviews."""
    text = "the cat and the hat and the bat"
    assert Counter(text.split()).most_common(1) == [("the", 3)]          # most frequent word
    assert list(dict.fromkeys([3, 1, 3, 2])) == [3, 1, 2]                # dedupe preserving order
    assert list(zip(*[(1, "a"), (2, "b")])) == [(1, 2), ("a", "b")]      # transpose / unzip
    assert max(range(5), key=lambda i: -abs(i - 3)) == 3                 # value closest to 3 (arg-max style)
    assert sum(1 for c in "banana" if c == "a") == 3                     # count matches with a generator
    assert "".join(sorted("listen")) == "".join(sorted("silent"))       # anagram check
    assert bin(5) == "0b101" and int("101", 2) == 5 and hex(255) == "0xff"   # number bases
    assert [*map(str, [1, 2])] == ["1", "2"] and list(reversed("abc")) == ["c", "b", "a"]


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    comprehensions()
    unpacking_and_swapping()
    itertools_tour()
    sorting_and_slicing()
    truthiness_and_comparison()
    walrus_and_match()
    useful_one_liners()
    print("08 comprehensions and itertools: all checks passed")
