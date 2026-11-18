"""02 - Functions: arguments, scope, closures, recursion, built-in helpers.

Run: python 02_functions.py
Each function demonstrates one concept and checks itself with assert.
"""
import functools
from functools import partial, reduce


def arguments():
    """Every kind of parameter: positional, default, *args, keyword-only, **kwargs, positional-only."""
    def f(a, b=2, *args, c, d=4, **kwargs):
        """Return every parameter exactly as received, to show how Python fills them."""
        # a: required positional | b: positional with a default | *args: extra positionals (a tuple)
        # c: keyword-only (it comes after *args) | d: keyword-only with a default | **kwargs: extra keywords (a dict)
        return a, b, args, c, d, kwargs

    assert f(1, c=3) == (1, 2, (), 3, 4, {})
    assert f(1, 9, 8, 7, c=3, z=0) == (1, 9, (8, 7), 3, 4, {"z": 0})

    def g(a, b, /, c):                              # the / means a and b are positional-only
        """Add three numbers; a and b cannot be passed by name."""
        return a + b + c
    assert g(1, 2, c=3) == 6

    nums = [1, 2, 3]
    opts = {"c": 5}
    assert f(*nums, **opts)[0:2] == (1, 2)          # * unpacks a list into positionals, ** unpacks a dict into keywords


def default_argument_trap():
    """Defaults are evaluated ONCE when the function is defined. Never use a mutable default."""
    def bad(x, items=[]):
        """Buggy: the same list object is reused by every call."""
        items.append(x)
        return items

    def good(x, items=None):
        """Correct: use None and create a fresh list inside."""
        items = [] if items is None else items
        items.append(x)
        return items

    bad(1)
    assert bad(2) == [1, 2]                         # the bug: state leaks between calls
    good(1)
    assert good(2) == [2]                           # fresh list each time


def first_class_functions():
    """Functions are objects: store them in variables, pass them around, return them."""
    def square(x):
        """Return x squared."""
        return x * x

    ops = {"sq": square, "neg": lambda x: -x}       # functions stored in a dict
    assert ops["sq"](4) == 16 and ops["neg"](4) == -4

    def apply_twice(fn, x):                         # higher-order function: takes a function as input
        """Call fn on x, then call fn on the result."""
        return fn(fn(x))
    assert apply_twice(square, 3) == 81

    def make_multiplier(n):                         # a function that returns a function
        """Return a function that multiplies its input by n."""
        return lambda x: x * n
    assert make_multiplier(3)(5) == 15


def closures_and_scope():
    """LEGB rule: names are looked up in Local, Enclosing, Global, then Built-in scope."""
    def counter():
        """Return an inc() function that remembers its own count between calls."""
        count = 0

        def inc():
            """Increase and return the count held in the enclosing scope."""
            nonlocal count                          # lets us REBIND count from the enclosing function
            count += 1
            return count
        return inc

    c = counter()
    assert (c(), c(), c()) == (1, 2, 3)             # the closure remembers `count`

    funcs = [lambda: i for i in range(3)]           # late binding gotcha: i is looked up when called
    assert [f() for f in funcs] == [2, 2, 2]        # all see the final value of i
    funcs = [lambda i=i: i for i in range(3)]       # fix: capture the current value as a default argument
    assert [f() for f in funcs] == [0, 1, 2]


TOTAL = 0                                           # module-level (global) variable


def global_keyword():
    """Increase the module-level TOTAL. `global` is required to REASSIGN a global name."""
    global TOTAL
    TOTAL += 1


def recursion():
    """Recursion = base case + a smaller version of the same problem. Default depth limit is ~1000."""
    def fact(n):
        """Factorial: n! = n * (n-1)!, with 1! = 1."""
        return 1 if n <= 1 else n * fact(n - 1)

    @functools.lru_cache(maxsize=None)              # memoization: cache results so each n is computed once
    def fib(n):
        """Fibonacci number; cached, so linear time instead of exponential."""
        return n if n < 2 else fib(n - 1) + fib(n - 2)

    assert fact(5) == 120 and fib(50) == 12586269025


def built_in_helpers():
    """map, filter, reduce, zip, enumerate, any, all, sorted, min, max, sum and friends."""
    nums = [1, 2, 3, 4]
    assert list(map(lambda x: x * 2, nums)) == [2, 4, 6, 8]          # transform every item
    assert list(filter(lambda x: x % 2 == 0, nums)) == [2, 4]        # keep items where the test is true
    assert reduce(lambda a, b: a + b, nums) == 10                    # fold the list into one value
    assert list(zip("ab", [1, 2])) == [("a", 1), ("b", 2)]           # pair items from two lists
    assert list(enumerate("ab", start=1)) == [(1, "a"), (2, "b")]    # index + value
    assert any(x > 3 for x in nums) and all(x > 0 for x in nums)     # at least one / every item
    assert sorted(["bb", "a", "ccc"], key=len, reverse=True)[0] == "ccc"
    assert max(["bb", "a"], key=len) == "bb" and sum(nums, 10) == 20 # sum(iterable, start)
    assert divmod(7, 2) == (3, 1) and abs(-3) == 3 and round(2.567, 1) == 2.6


def partial_application():
    """functools.partial: create a new function with some arguments already fixed."""
    power = lambda base, exp: base ** exp
    square = partial(power, exp=2)                  # exp is now always 2
    assert square(5) == 25


def type_hints_and_docstrings(items: list[int], scale: float = 1.0) -> list[float]:
    """Type hints are not enforced at runtime; tools (mypy, IDEs) use them.

    Args:
        items: numbers to scale.
        scale: multiplier.
    Returns:
        the scaled numbers.
    """
    return [i * scale for i in items]


def pass_by_object_reference():
    """Python passes references to objects: mutating shows outside, rebinding does not."""
    def mutate(lst):
        """Changes the caller's list in place."""
        lst.append(99)

    def rebind(lst):
        """Points the local name at a new list; the caller's list is untouched."""
        lst = [0]
        return lst

    a = [1]
    mutate(a)
    rebind(a)
    assert a == [1, 99]


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    for fn in (arguments, default_argument_trap, first_class_functions, closures_and_scope,
               recursion, built_in_helpers, partial_application, pass_by_object_reference):
        fn()
    global_keyword()
    assert TOTAL == 1
    assert type_hints_and_docstrings([1, 2], 2) == [2, 4]
    print("02 functions: all checks passed")
