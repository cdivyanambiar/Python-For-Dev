"""04 - Iterators and generators.

Iterator: object with __iter__ and __next__. Generator: a function with `yield` that Python
turns into an iterator for you. Values are produced lazily, one at a time, so memory stays
constant even for huge or infinite streams (log files, telemetry).

Run: python 04_generators.py
Sections are numbered 1-10; the checks are in the __main__ block at the bottom.
"""
import itertools
import sys
from contextlib import contextmanager


# 1. Generator function
def countdown(n):
    """Yield n, n-1, ... 1, one value per next() call."""
    while n > 0:
        yield n                                     # pauses here, resumes on the next next()
        n -= 1


# 2. Generator expression (lazy) vs list comprehension (eager)
def expression_vs_list():
    """Compare memory use and show that a generator can be consumed only once."""
    lst = [x * x for x in range(1000)]              # builds all 1000 values now
    gen = (x * x for x in range(1000))              # builds nothing yet
    assert sys.getsizeof(gen) < sys.getsizeof(lst)  # the generator object is tiny
    assert sum(gen) == sum(lst)
    assert sum(gen) == 0                            # already exhausted: a generator is single-pass


# 3. Reading a big file / log stream line by line
def read_logs(lines, level):
    """Yield only the lines that start with `level` (in real life: `for line in open(path)`)."""
    for line in lines:
        if line.startswith(level):
            yield line.strip()


# 4. Pipelines: chain generators, nothing is materialised until the end
def parse(lines):
    """Yield [level, message] for each 'LEVEL:message' line."""
    for line in lines:
        yield line.split(":", 1)


def only_errors(records):
    """Yield the message of ERROR records only."""
    for level, msg in records:
        if level == "ERROR":
            yield msg


# 5. Infinite generator + islice
def fibonacci():
    """Yield the Fibonacci numbers forever; the caller decides when to stop (e.g. islice)."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


# 6. yield from: delegate to another iterable
def flatten(nested):
    """Yield every non-list item from arbitrarily nested lists."""
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)                # hand over to the inner generator
        else:
            yield item


# 7. send(): generators can receive values (coroutine style, e.g. running average)
def running_average():
    """Receive numbers via send() and yield the running average."""
    total, count, avg = 0.0, 0, None
    while True:
        value = yield avg                           # hand back the current average, wait for the next value
        total += value
        count += 1
        avg = total / count


# 8. Sliding window and batching: very common in data code
def sliding_window(seq, size):
    """Yield consecutive windows of `size` items: (1,2), (2,3), ..."""
    window = []
    for x in seq:
        window.append(x)
        if len(window) == size:
            yield tuple(window)
            window.pop(0)                           # slide forward by one


def batched(iterable, n):
    """Yield lists of up to n items (useful for bulk inserts and API calls)."""
    it = iter(iterable)
    while batch := list(itertools.islice(it, n)):   # walrus operator (3.8+): assign and test in one step
        yield batch


# 9. Custom iterator class (what a generator does for you)
class Countdown:
    """The same countdown written as an iterator class, to show what `yield` saves you."""

    def __init__(self, n):
        """Start counting down from n."""
        self.n = n

    def __iter__(self):
        """An iterator returns itself, so it can be used in a for loop."""
        return self

    def __next__(self):
        """Return the next value, or raise StopIteration when finished."""
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


# 10. Context manager with a generator
@contextmanager
def opened(log):
    """Context manager: record 'open' on entry and 'close' on exit, even if the body fails."""
    log.append("open")
    try:
        yield "resource"                            # the value bound by `as`; the with-body runs here
    finally:
        log.append("close")                         # always runs, even on error


if __name__ == "__main__":
    # 1. basic generator, manual next(), StopIteration, next with a default
    assert list(countdown(3)) == [3, 2, 1]
    g = countdown(2)
    assert next(g) == 2 and next(g) == 1
    try:
        next(g)
        raise AssertionError
    except StopIteration:                           # raised when the generator is exhausted
        pass
    assert next(g, "done") == "done"                # a default value avoids the exception
    # 2. lazy vs eager
    expression_vs_list()

    # 3-4. file-style reading and a pipeline of generators
    logs = ["ERROR:disk full", "INFO:ok", "ERROR:cpu hot"]
    assert list(read_logs(logs, "ERROR")) == ["ERROR:disk full", "ERROR:cpu hot"]
    assert list(only_errors(parse(logs))) == ["disk full", "cpu hot"]
    # 5-6. infinite sequence cut with islice; recursive flatten
    assert list(itertools.islice(fibonacci(), 8)) == [0, 1, 1, 2, 3, 5, 8, 13]
    assert list(flatten([1, [2, [3, 4]], 5])) == [1, 2, 3, 4, 5]

    # 7. send(): "prime" the generator with next() first, then push values in
    avg = running_average()
    next(avg)
    assert avg.send(10) == 10 and avg.send(20) == 15

    # 8-9. windows, batches and the class-based iterator
    assert list(sliding_window([1, 2, 3, 4], 2)) == [(1, 2), (2, 3), (3, 4)]
    assert list(batched(range(5), 2)) == [[0, 1], [2, 3], [4]]
    assert list(Countdown(3)) == [3, 2, 1]

    # 10. generator-based context manager
    log = []
    with opened(log) as r:
        assert r == "resource"
    assert log == ["open", "close"]
    print("04 generators: all checks passed")

# Interview talking points:
#  - Why generators? Lazy evaluation, constant memory, can model infinite streams, composable pipelines.
#  - Generator vs list: a generator is single-pass and cannot be indexed or len()'d.
#  - `return` inside a generator ends it (StopIteration); `yield from` delegates; `send()` pushes values in.
#  - Related: itertools (islice, chain, groupby, product, combinations, accumulate).
