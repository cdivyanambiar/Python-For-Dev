"""05 - Lambda: small anonymous, single-expression functions.

Syntax: lambda arguments: expression      (no statements, no assignment, returns the expression)
Use for short throwaway functions, mostly as key= / callback arguments. For anything longer, use def.

Run: python 05_lambda.py
"""
from functools import reduce


def basics():
    """Lambda syntax: parameters, defaults, *args/**kwargs and conditional expressions."""
    add = lambda a, b: a + b                        # same as def add(a, b): return a + b
    assert add(2, 3) == 5
    assert (lambda x: x * 2)(4) == 8                # define and call immediately
    default = lambda x, y=10: x + y                 # default values work
    assert default(1) == 11
    var = lambda *args, **kw: (args, kw)            # variable arguments work
    assert var(1, a=2) == ((1,), {"a": 2})
    sign = lambda n: "pos" if n > 0 else "neg" if n < 0 else "zero"   # conditional expression instead of if/else
    assert (sign(5), sign(-1), sign(0)) == ("pos", "neg", "zero")


def with_sorted_min_max():
    """The most common use: key=lambda for sorted, min and max."""
    people = [("ann", 30), ("bob", 25), ("cy", 35)]
    assert sorted(people, key=lambda p: p[1])[0] == ("bob", 25)       # sort by age
    assert max(people, key=lambda p: p[1]) == ("cy", 35)              # oldest person
    words = ["pear", "fig", "banana"]
    assert sorted(words, key=lambda w: (len(w), w)) == ["fig", "pear", "banana"]   # tuple key = sort by length, then alphabetically
    assert sorted(people, key=lambda p: (-p[1], p[0]))[0] == ("cy", 35)            # minus sign = descending for numbers
    d = {"a": 3, "b": 1}
    assert sorted(d.items(), key=lambda kv: kv[1])[0] == ("b", 1)     # dict items ordered by value


def with_map_filter_reduce():
    """Lambda with map, filter and reduce, and the comprehension that is usually clearer."""
    nums = [1, 2, 3, 4, 5]
    assert list(map(lambda x: x ** 2, nums)) == [1, 4, 9, 16, 25]     # transform
    assert list(filter(lambda x: x % 2, nums)) == [1, 3, 5]           # keep odd numbers (x % 2 is 1 = truthy)
    assert reduce(lambda a, b: a * b, nums) == 120                    # multiply all together
    assert [x ** 2 for x in nums if x % 2] == [1, 9, 25]              # comprehension: map + filter in one


def with_pandas_style():
    """Same idea as df.apply(lambda ...) and df.sort_values(key=...)."""
    rows = [{"device": "a", "bytes": 10}, {"device": "b", "bytes": 900}]
    big = list(filter(lambda r: r["bytes"] > 100, rows))
    assert big == [{"device": "b", "bytes": 900}]
    to_mb = lambda b: b / 1_000_000                 # convert bytes to megabytes
    assert to_mb(5_000_000) == 5


def callbacks_and_dispatch():
    """A dict of lambdas replaces a long if/elif chain; lambdas can also be closures."""
    ops = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
    }
    assert ops["mul"](3, 4) == 12                   # look up the operation by name and call it

    def make_adder(n):
        """Return a lambda that remembers n (a closure)."""
        return lambda x: x + n
    assert make_adder(5)(1) == 6


def gotchas():
    """Late binding: a lambda looks the variable up when CALLED, not when defined."""
    fs = [lambda: i for i in range(3)]
    assert [f() for f in fs] == [2, 2, 2]           # every lambda sees the final i
    fs = [lambda i=i: i for i in range(3)]          # fix: capture the current value with a default argument
    assert [f() for f in fs] == [0, 1, 2]
    # Don't assign a lambda to a name just to reuse it: PEP 8 prefers def (better tracebacks, docstrings)


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    basics()
    with_sorted_min_max()
    with_map_filter_reduce()
    with_pandas_style()
    callbacks_and_dispatch()
    gotchas()
    print("05 lambda: all checks passed")

# Interview talking points:
#  - Lambda = anonymous function limited to ONE expression.
#  - Typical use: sort/max/min keys, map/filter, callbacks, small dispatch tables, pandas apply.
#  - Limits: no statements, no annotations, hard to debug if complex. Prefer def or a comprehension then.
