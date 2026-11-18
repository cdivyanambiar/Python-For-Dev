"""06 - OOP: classes, inheritance, dunder methods, properties, ABCs, composition.

Run: python 06_oop.py
The classes are defined first; the checks are in the __main__ block at the bottom.
"""
from abc import ABC, abstractmethod
from functools import total_ordering


class Device:
    """Basic class. A class attribute is shared by all objects; instance attributes belong to each object."""

    count = 0                                       # class attribute: shared by every Device

    def __init__(self, name, temp=20.0):
        """Constructor: runs when you write Device("gw1").

        Args:
            name: device name (public attribute).
            temp: temperature in Celsius.
        """
        self.name = name                            # public attribute
        self._temp = temp                           # single underscore = "protected" by convention only
        self.__secret = "x"                         # double underscore = name-mangled to _Device__secret
        Device.count += 1                           # update the shared counter

    def __repr__(self):
        """Developer-friendly text, shown in the debugger and the REPL. Aim for code that recreates the object."""
        return f"Device({self.name!r}, {self._temp})"

    def __str__(self):
        """User-friendly text, used by print() and str()."""
        return f"{self.name} @ {self._temp}C"

    @property                                       # getter: lets you write d.temp instead of d.get_temp()
    def temp(self):
        """Current temperature."""
        return self._temp

    @temp.setter                                    # setter: runs on d.temp = value, so we can validate
    def temp(self, value):
        """Set the temperature, rejecting impossible values."""
        if value < -273.15:
            raise ValueError("below absolute zero")
        self._temp = value

    @classmethod                                    # receives the class (cls); good for alternative constructors
    def from_string(cls, s):
        """Build a Device from text such as "gw2,25"."""
        name, temp = s.split(",")
        return cls(name, float(temp))               # cls(...) also works for subclasses

    @staticmethod                                   # no self/cls: just a helper grouped with the class
    def c_to_f(c):
        """Convert Celsius to Fahrenheit."""
        return c * 9 / 5 + 32


class Router(Device):
    """Inheritance: reuse and extend a parent class. super() calls the parent."""

    def __init__(self, name, temp=20.0, ports=4):
        """Initialise the Device part first, then add router-specific data."""
        super().__init__(name, temp)
        self.ports = ports

    def __str__(self):
        """Override the parent's text and extend it."""
        return f"Router {super().__str__()} ({self.ports} ports)"


class Shape(ABC):
    """Abstract base class: cannot be instantiated; forces subclasses to implement the abstract methods."""

    @abstractmethod
    def area(self):
        """Every concrete shape must provide its area."""
        ...


class Square(Shape):
    """Concrete shape implementing the required method."""

    def __init__(self, s):
        """s is the side length."""
        self.s = s

    def area(self):                                 # polymorphism: same call, different behaviour per class
        """Area of the square."""
        return self.s ** 2


@total_ordering                                     # fills in <=, >, >= from __eq__ and __lt__
class Version:
    """Comparable version number, e.g. Version(1, 10) > Version(1, 2)."""

    def __init__(self, *parts):
        """parts: the numbers of the version, e.g. (1, 2, 3)."""
        self.parts = parts

    def __eq__(self, other):
        """Equal when all parts are equal."""
        return self.parts == other.parts

    def __lt__(self, other):
        """Tuple comparison gives the right ordering (1, 2) < (1, 10)."""
        return self.parts < other.parts

    def __hash__(self):
        """Defining __eq__ removes the default hash; add it back so versions can go in sets and dict keys."""
        return hash(self.parts)


class Vector:
    """Operator overloading and the container protocol."""

    def __init__(self, *xs):
        """xs: the components of the vector."""
        self.xs = list(xs)

    def __add__(self, other):
        """Implements v1 + v2 (component-wise)."""
        return Vector(*[a + b for a, b in zip(self.xs, other.xs)])

    def __len__(self):
        """Implements len(v)."""
        return len(self.xs)

    def __getitem__(self, i):                       # also enables slicing and iteration
        """Implements v[i]."""
        return self.xs[i]

    def __contains__(self, x):
        """Implements `x in v`."""
        return x in self.xs

    def __bool__(self):
        """Implements bool(v): false when all components are zero."""
        return any(self.xs)

    def __call__(self, k):                          # makes the object callable like a function
        """Implements v(k): scale the vector by k."""
        return Vector(*[x * k for x in self.xs])

    def __enter__(self):                            # context manager protocol: start of the `with` block
        """Return the object that `as` binds to."""
        return self

    def __exit__(self, exc_type, exc, tb):          # end of the `with` block
        """Cleanup would go here. Returning False means exceptions are NOT swallowed."""
        return False


class Engine:
    """A part of a car."""

    def start(self):
        """Start the engine."""
        return "vroom"


class Car:
    """Composition ("has a") is often better than inheritance ("is a")."""

    def __init__(self):
        """A car owns an engine."""
        self.engine = Engine()

    def start(self):
        """Delegate to the engine."""
        return self.engine.start()


class Slim:
    """__slots__: fixed attributes and no per-instance __dict__, so millions of objects use less memory."""

    __slots__ = ("a", "b")

    def __init__(self, a, b):
        """Only the attributes listed in __slots__ are allowed."""
        self.a, self.b = a, b


if __name__ == "__main__":
    # Device: class counter, __repr__/__str__, property with validation
    d = Device("gw1")
    assert Device.count == 1 and repr(d) == "Device('gw1', 20.0)" and str(d) == "gw1 @ 20.0C"
    d.temp = 30
    assert d.temp == 30
    try:
        d.temp = -500                               # the setter rejects it
        raise AssertionError
    except ValueError:
        pass
    # classmethod, staticmethod and name mangling
    assert Device.from_string("gw2,25").temp == 25.0 and Device.c_to_f(100) == 212
    assert d._Device__secret == "x"                 # mangling is not real security

    # Inheritance and method resolution order
    r = Router("r1", ports=8)
    assert isinstance(r, Device) and issubclass(Router, Device) and "8 ports" in str(r)
    assert Router.__mro__[1] is Device              # the order Python searches classes for a method

    # Abstract class cannot be instantiated; the concrete one works
    try:
        Shape()
        raise AssertionError
    except TypeError:
        pass
    assert Square(3).area() == 9

    # Operator overloading and the container protocol
    assert Version(1, 2) < Version(1, 10) and Version(2) >= Version(1, 9)
    v = Vector(1, 2) + Vector(3, 4)
    assert v.xs == [4, 6] and len(v) == 2 and v[0] == 4 and 6 in v and bool(v) and v(2).xs == [8, 12]
    with Vector(1) as vv:                           # uses __enter__ / __exit__
        assert vv.xs == [1]
    # Composition and __slots__
    assert Car().start() == "vroom"
    s = Slim(1, 2)
    try:
        s.c = 3                                     # not in __slots__
        raise AssertionError
    except AttributeError:
        pass
    print("06 oop: all checks passed")

# Interview talking points:
#  - The four pillars: encapsulation, inheritance, polymorphism, abstraction.
#  - __repr__ vs __str__; @property for validated attributes; classmethod vs staticmethod.
#  - Prefer composition; use ABC to define interfaces; dataclasses (file 01) for plain records.
#  - Python supports multiple inheritance (MRO via C3 linearisation); super() follows the MRO.
