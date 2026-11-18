# Built-in & Standard-Library Decorators – Cheat Sheet

A **decorator** is a function that takes a function (or class) and returns a new one.

```python
@deco
def f(): ...
# is exactly the same as
f = deco(f)
```

See [03_decorators.py](./03_decorators.py) for how to write your own decorators.

---

## 1. Built-in (no import needed)

| Decorator | What it does |
|---|---|
| `@property` | Lets you call a method like an attribute (`obj.area` instead of `obj.area()`). Add `@x.setter` / `@x.deleter` to control writes. |
| `@staticmethod` | A method that gets neither `self` nor `cls`; it's a plain function that lives inside the class. |
| `@classmethod` | Receives the class (`cls`) instead of the instance. Common use: alternate constructors such as `from_json`. |

```python
class Circle:
    def __init__(self, r):
        self._r = r

    @property
    def radius(self):
        return self._r

    @radius.setter
    def radius(self, v):
        if v < 0:
            raise ValueError("negative radius")
        self._r = v

    @classmethod
    def unit(cls):                      # alternate constructor
        return cls(1)

    @staticmethod
    def area_of(r):                     # utility, no self/cls
        return 3.14159 * r * r


c = Circle.unit()
c.radius = 5                            # goes through the setter
print(c.radius, Circle.area_of(2))
```

---

## 2. Standard library

| Decorator | Module | What it does |
|---|---|---|
| `@dataclass` | `dataclasses` | Generates `__init__`, `__repr__` and `__eq__` from the fields you declare. Options: `frozen=True` (immutable), `order=True` (adds `<`, `>`), `slots=True` (less memory). |
| `@lru_cache(maxsize=128)` | `functools` | Caches function results (memoization). |
| `@cache` | `functools` | Same as `lru_cache`, but with no size limit. |
| `@cached_property` | `functools` | A property that is computed once, then stored on the instance. |
| `@wraps(func)` | `functools` | Use inside your own decorators so the wrapped function keeps its name and docstring. |
| `@total_ordering` | `functools` | Define `__eq__` plus one comparison (e.g. `__lt__`) and it fills in the rest. |
| `@singledispatch` | `functools` | Runs a different version of a function depending on the type of its first argument. |
| `@contextmanager` | `contextlib` | Turns a generator into a `with` context manager. |
| `@abstractmethod` | `abc` | Marks a method that subclasses must implement (the class must inherit from `ABC`). |
| `@overload`, `@final`, `@override` | `typing` | Hints for type checkers (mypy) only; they don't change runtime behaviour. |
| `@unique` | `enum` | Raises an error if two Enum members have the same value. |
| `@atexit.register` | `atexit` | Runs the function when the program exits. |
| `@patch(...)` | `unittest.mock` | Replaces an object with a mock while a test runs. |
| `@skip(...)` / `@skipIf(...)` | `unittest` | Skips a test (optionally only when a condition is true). |

### @dataclass

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, order=True)
class Reading:
    device: str
    value: float
    tags: list = field(default_factory=list)   # never use a mutable default like tags=[]

r = Reading("sensor-1", 21.5)
print(r)                                       # Reading(device='sensor-1', value=21.5, tags=[])
```

### @lru_cache / @cache

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(80))              # instant, because results are cached
print(fib.cache_info())     # hits, misses, size
```

### @cached_property

```python
from functools import cached_property

class Report:
    def __init__(self, rows):
        self.rows = rows

    @cached_property
    def total(self):            # expensive work runs only on first access
        print("computing...")
        return sum(self.rows)

r = Report([1, 2, 3])
r.total; r.total                # prints "computing..." once
```

### @wraps (when writing your own decorator)

```python
from functools import wraps

def retry(times):
    def deco(func):
        @wraps(func)                       # keeps func.__name__ and __doc__
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == times - 1:
                        raise
        return wrapper
    return deco

@retry(3)
def call_api():
    """Calls a flaky API."""
    ...

print(call_api.__name__)                   # 'call_api' (would be 'wrapper' without @wraps)
```

### @total_ordering

```python
from functools import total_ordering

@total_ordering
class Version:
    def __init__(self, major, minor):
        self.key = (major, minor)
    def __eq__(self, other):
        return self.key == other.key
    def __lt__(self, other):
        return self.key < other.key

print(Version(1, 2) >= Version(1, 0))      # True; >= was generated for us
```

### @singledispatch

```python
from functools import singledispatch

@singledispatch
def to_json(obj):
    raise TypeError(f"unsupported type {type(obj)}")

@to_json.register
def _(obj: int):
    return str(obj)

@to_json.register
def _(obj: list):
    return "[" + ",".join(to_json(x) for x in obj) + "]"

print(to_json([1, 2, 3]))                  # [1,2,3]
```

### @contextmanager

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name):
    start = time.perf_counter()
    try:
        yield                              # the body of the `with` block runs here
    finally:
        print(f"{name}: {time.perf_counter() - start:.3f}s")

with timer("work"):
    sum(range(1_000_000))
```

### @abstractmethod

```python
from abc import ABC, abstractmethod

class Detector(ABC):
    @abstractmethod
    def detect(self, data): ...

class ThresholdDetector(Detector):
    def detect(self, data):
        return [x for x in data if x > 90]

# Detector() -> TypeError: can't instantiate abstract class
print(ThresholdDetector().detect([50, 95]))
```

### @unique (Enum)

```python
from enum import Enum, unique

@unique
class Status(Enum):
    ONLINE = 1
    OFFLINE = 2
    # DOWN = 2   -> ValueError: duplicate values found
```

### @patch (testing)

```python
from unittest.mock import patch

@patch("time.sleep", return_value=None)    # don't really sleep in tests
def test_fast(mock_sleep):
    import time
    time.sleep(10)
    mock_sleep.assert_called_once_with(10)
```

---

## 3. Common in third-party libraries

| Library | Decorators |
|---|---|
| pytest | `@pytest.fixture`, `@pytest.mark.parametrize`, `@pytest.mark.skip` |
| FastAPI | `@app.get("/path")`, `@app.post(...)`, `@app.on_event(...)` |
| Flask | `@app.route("/")` |
| PyTorch | `@torch.no_grad()`, `@torch.inference_mode()`, `@torch.compile` |
| Airflow | `@dag`, `@task` |
| Celery | `@app.task` |
| Click | `@click.command()`, `@click.option(...)` |

---

## 4. Interview quick facts

- Decorators run **once, at definition time**; the wrapper they return runs on **every call**.
- Stacked decorators apply **bottom-up**: `@a @b def f` → `f = a(b(f))`.
- A decorator with arguments (`@retry(3)`) is a **function that returns a decorator**, so there are three nested levels.
- Always use `@functools.wraps` in custom decorators to keep the function's name and docstring.
- `@staticmethod` vs `@classmethod`: use `classmethod` when you need the class (factories, inheritance-aware behaviour); use `staticmethod` for plain helpers.
- `@property` vs `@cached_property`: `property` recomputes on every access; `cached_property` computes once per instance.
- Class decorators (like `@dataclass`) take a **class** and return a (modified) class.
