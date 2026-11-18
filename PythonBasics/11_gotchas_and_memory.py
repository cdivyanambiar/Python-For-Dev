"""11 - Gotchas and memory model: the classic "what does this print?" interview questions.

Run: python 11_gotchas_and_memory.py
Each function shows one surprising behaviour and asserts what really happens.
"""
import copy
import sys


def identity_vs_equality():
    """== compares values; `is` asks whether two names point to the very same object."""
    a, b = [1, 2], [1, 2]
    assert a == b and a is not b                    # same content, different objects
    c = a
    assert c is a                                   # c is just another name for the same list
    x = None
    assert x is None                                # always use `is` for None


def mutable_vs_immutable():
    """Immutable: int, float, str, tuple, frozenset, bytes. Mutable: list, dict, set, bytearray."""
    s = "abc"
    t = s
    s += "d"                                        # creates a NEW string; t still points to the old one
    assert t == "abc"
    lst = [1]
    alias = lst
    lst += [2]                                      # mutates the same list in place; alias sees the change
    assert alias == [1, 2]
    tup = ([1], 2)
    tup[0].append(9)                                # the tuple is immutable, but the list inside it is not
    assert tup == ([1, 9], 2)


def shallow_vs_deep_copy():
    """copy.copy copies only the outer container; deepcopy copies everything inside too."""
    orig = [[1, 2], [3]]
    shallow = copy.copy(orig)                       # same as orig[:] or list(orig)
    deep = copy.deepcopy(orig)
    orig[0].append(99)
    assert shallow[0] == [1, 2, 99]                 # the inner list is shared with orig
    assert deep[0] == [1, 2]                        # fully independent


def list_multiplication_trap():
    """[[0]*2]*2 repeats a reference to ONE inner list."""
    bad = [[0] * 2] * 2                             # both rows are the same list object
    bad[0][0] = 1
    assert bad == [[1, 0], [1, 0]]
    good = [[0] * 2 for _ in range(2)]              # a comprehension makes a new row each time
    good[0][0] = 1
    assert good == [[1, 0], [0, 0]]


def modifying_while_iterating():
    """Removing items from a list while looping over it skips elements."""
    nums = [1, 2, 3, 4]
    for n in nums[:]:                               # loop over a COPY (nums[:]) while changing nums
        if n % 2 == 0:
            nums.remove(n)
    assert nums == [1, 3]
    assert [n for n in [1, 2, 3, 4] if n % 2] == [1, 3]   # better: build a new list


def small_int_caching():
    """CPython reuses small integers, so `is` can look like it works. Never rely on it for numbers."""
    a, b = 256, 256
    assert a is b                                   # small ints (-5..256) are cached
    assert sys.getrefcount([]) >= 1                 # memory is managed by reference counting plus a cycle-detecting GC


def float_precision():
    """Binary floating point cannot store 0.1 exactly; and round() uses banker's rounding."""
    assert 0.1 + 0.2 != 0.3 and abs(0.1 + 0.2 - 0.3) < 1e-9   # compare with a tolerance
    assert round(0.5) == 0 and round(1.5) == 2 and round(2.5) == 2   # round half to even


def dict_and_hashing():
    """Keys that are equal AND have the same hash are the same key; lists are unhashable."""
    d = {}
    d[1] = "int"
    d[1.0] = "float"                                # 1 == 1.0 and their hashes are equal -> same key
    d[True] = "bool"                                # True == 1 as well
    assert d == {1: "bool"}                         # one key, last value wins
    try:
        {[1]: 2}                                    # lists are mutable, so they are unhashable
        raise AssertionError
    except TypeError:
        pass


def string_gotchas():
    """Operators on strings, and characters vs bytes."""
    assert "abc" * 2 == "abcabc" and "a" in "abc" and "".join(["a", "b"]) == "ab"
    assert "x".isdigit() is False and "٣".isdigit()  # Arabic-Indic digit three counts as a digit
    assert len("é") == 1 and len("é".encode("utf-8")) == 2   # characters vs bytes


def default_and_class_attribute_trap():
    """A list defined at class level is shared by all instances."""
    class A:
        """Demo class with a shared class attribute."""
        items = []                                  # class attribute: ONE list for every instance

        def add(self, x):
            """Append to the shared list."""
            self.items.append(x)

    a1, a2 = A(), A()
    a1.add(1)
    assert a2.items == [1]                          # surprise: a2 sees a1's change (create the list in __init__ instead)


def generator_exhaustion():
    """A generator can be consumed only once."""
    g = (x for x in range(3))
    assert list(g) == [0, 1, 2] and list(g) == []   # the second pass is empty


def try_finally_return():
    """`finally` runs before the function returns, and a return inside it overrides everything."""
    def f():
        """Returns 'try' after running the finally block."""
        try:
            return "try"
        finally:
            pass                                    # runs before the function actually returns
    assert f() == "try"

    def g():
        """Return in finally replaces the earlier return (avoid this)."""
        try:
            return "try"
        finally:
            return "finally"
    assert g() == "finally"


def sort_stability_and_key():
    """sorted() is stable: items with equal keys keep their original order."""
    people = [("b", 1), ("a", 1), ("c", 0)]
    assert sorted(people, key=lambda p: p[1]) == [("c", 0), ("b", 1), ("a", 1)]   # b stays before a


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    for fn in (identity_vs_equality, mutable_vs_immutable, shallow_vs_deep_copy, list_multiplication_trap,
               modifying_while_iterating, small_int_caching, float_precision, dict_and_hashing,
               string_gotchas, default_and_class_attribute_trap, generator_exhaustion,
               try_finally_return, sort_stability_and_key):
        fn()
    print("11 gotchas: all checks passed")
