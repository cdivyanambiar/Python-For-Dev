"""03 - Decorators.

A decorator is a function that takes a function, wraps it with extra behaviour and returns
the wrapper. `@deco` above `def f` is the same as `f = deco(f)`.

Run: python 03_decorators.py
Sections are numbered 1-8; the checks are in the __main__ block at the bottom.
"""
import functools
import time


# 1. The basic pattern
def shout(fn):
    """Decorator: make the wrapped function return its text in upper case."""
    @functools.wraps(fn)                            # keeps the original __name__ and __doc__
    def wrapper(*args, **kwargs):                   # accept any arguments and pass them through
        """Call fn, then upper-case the result."""
        return fn(*args, **kwargs).upper()          # extra behaviour around the call
    return wrapper                                  # the wrapper replaces the original function


@shout
def greet(name):
    """Say hello."""
    return f"hello {name}"


# 2. Decorator WITH arguments: one more level (a factory that returns the decorator)
def retry(times=3, delay=0.0, exceptions=(Exception,)):
    """Decorator factory: retry the function up to `times` times if it raises.

    Args:
        times: maximum attempts.
        delay: seconds to wait between attempts.
        exceptions: exception types that trigger a retry.
    """
    def deco(fn):
        """The real decorator, with `times`, `delay` and `exceptions` captured from the factory."""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            """Try fn repeatedly; re-raise on the final failure."""
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions:
                    if attempt == times:            # out of attempts: let the error escape
                        raise
                    time.sleep(delay)
        return wrapper
    return deco


CALLS = {"n": 0}                                    # counts how often flaky() ran


@retry(times=3)
def flaky():
    """Fails twice, then succeeds: shows retry in action."""
    CALLS["n"] += 1
    if CALLS["n"] < 3:
        raise RuntimeError("temporary failure")
    return "ok"


# 3. Timing decorator
def timed(fn):
    """Decorator: record how long each call takes in `wrapper.last_seconds`."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        """Time the call to fn."""
        start = time.perf_counter()                 # high-resolution clock
        try:
            return fn(*args, **kwargs)
        finally:                                    # runs even if fn raises
            wrapper.last_seconds = time.perf_counter() - start
    wrapper.last_seconds = None                     # functions are objects, so they can hold attributes
    return wrapper


@timed
def slow_sum(n):
    """Sum 0..n-1 (a stand-in for slow work)."""
    return sum(range(n))


# 4. Memoize (cache): same idea as functools.lru_cache
def memoize(fn):
    """Decorator: remember results by arguments so repeated calls are instant."""
    cache = {}                                      # lives in the closure, shared by every call

    @functools.wraps(fn)
    def wrapper(*args):
        """Look in the cache first; compute only on a miss."""
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    wrapper.cache = cache                           # expose the cache so we can inspect it
    return wrapper


@memoize
def fib(n):
    """Fibonacci; without the cache this would be exponential."""
    return n if n < 2 else fib(n - 1) + fib(n - 2)


# 5. Access control / approval gate (like the Cisco IoT assistant)
def require_role(role):
    """Decorator factory: only users that have `role` may call the function."""
    def deco(fn):
        """The decorator that applies the permission check."""
        @functools.wraps(fn)
        def wrapper(user, *args, **kwargs):
            """Raise PermissionError unless the user has the role."""
            if role not in user.get("roles", []):
                raise PermissionError(f"{role} role required")
            return fn(user, *args, **kwargs)
        return wrapper
    return deco


@require_role("admin")
def delete_sim(user, sim_id):
    """Risky action that only admins may run."""
    return f"deleted {sim_id}"


# 6. Stacking decorators: applied bottom-up, executed top-down
def tag(name):
    """Decorator factory: wrap the result in <name>...</name>."""
    def deco(fn):
        """The decorator that adds the tag."""
        @functools.wraps(fn)
        def wrapper(*a, **k):
            """Call fn and wrap its result."""
            return f"<{name}>{fn(*a, **k)}</{name}>"
        return wrapper
    return deco


@tag("b")                                           # applied second (outer)
@tag("i")                                           # applied first (inner)
def text():
    """Returns plain text; the decorators add the tags."""
    return "hi"


# 7. Class-based decorator (keeps state in the object)
class CountCalls:
    """Decorator written as a class: counts how many times the function was called."""

    def __init__(self, fn):
        """Receive the function being decorated."""
        functools.update_wrapper(self, fn)          # copy name and docstring onto the object
        self.fn, self.count = fn, 0

    def __call__(self, *args, **kwargs):            # makes the object callable like a function
        """Count the call and delegate to the real function."""
        self.count += 1
        return self.fn(*args, **kwargs)


@CountCalls
def ping():
    """Trivial function to count calls of."""
    return "pong"


# 8. Built-in decorators used on class methods
class Temperature:
    """Celsius temperature showing @property, @staticmethod, @classmethod and cached_property."""

    def __init__(self, c):
        """Store the temperature in Celsius."""
        self._c = c

    @property                                       # attribute-style access to a method: t.fahrenheit
    def fahrenheit(self):
        """Temperature in Fahrenheit, computed on access."""
        return self._c * 9 / 5 + 32

    @staticmethod                                   # no self/cls: a plain function in the class namespace
    def is_valid(c):
        """Is c above absolute zero?"""
        return c > -273.15

    @classmethod                                    # receives the class: alternative constructors
    def from_f(cls, f):
        """Build a Temperature from Fahrenheit."""
        return cls((f - 32) * 5 / 9)

    @functools.cached_property                      # computed once, then stored on the instance (3.8+)
    def expensive(self):
        """Pretend this is slow; it runs only the first time."""
        return self._c * 1000


if __name__ == "__main__":
    # 1. wraps preserved the name/doc while the output is upper-cased
    assert greet("ann") == "HELLO ANN" and greet.__name__ == "greet" and greet.__doc__ == "Say hello."
    # 2. flaky failed twice and the third attempt succeeded
    assert flaky() == "ok" and CALLS["n"] == 3
    # 3. timing was recorded
    assert slow_sum(1000) == 499500 and slow_sum.last_seconds >= 0
    # 4. cache holds fib(0)..fib(60): 61 entries
    assert fib(60) == 1548008755920 and len(fib.cache) == 61
    # 5. admins pass, others are denied
    assert delete_sim({"roles": ["admin"]}, "s1") == "deleted s1"
    try:
        delete_sim({"roles": []}, "s1")
        raise AssertionError("should have been denied")
    except PermissionError:
        pass
    # 6. inner decorator runs first, outer wraps it
    assert text() == "<b><i>hi</i></b>"
    # 7. the class-based decorator counted two calls
    ping(), ping()
    assert ping.count == 2
    # 8. classmethod builds from F; property converts back; cached_property computes once
    t = Temperature.from_f(212)
    assert round(t.fahrenheit) == 212 and Temperature.is_valid(0) and t.expensive == 100000
    print("03 decorators: all checks passed")

# Interview talking points:
#  - Why functools.wraps? Without it the wrapper hides the original name/docstring (breaks debugging, docs, pickling).
#  - Decorator with arguments = 3 nested functions (factory -> decorator -> wrapper).
#  - Passing a function as an argument (callback) is NOT a decorator; a decorator RETURNS a wrapped function.
#  - Typical uses: logging, timing, retry, caching, auth/permission checks, rate limiting, registering routes.
