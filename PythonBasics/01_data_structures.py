"""01 - Data structures: built-ins + the collections/heapq/bisect extras interviewers expect.

Run: python 01_data_structures.py
Each function demonstrates one structure and checks itself with assert.
The Big-O cheat sheet is at the bottom.
"""
import bisect
import heapq
from collections import ChainMap, Counter, OrderedDict, defaultdict, deque, namedtuple
from dataclasses import dataclass, field


def lists():
    """list: ordered, mutable, allows duplicates. Implemented as a dynamic array."""
    a = [3, 1, 2]
    a.append(4)             # add at the end                 O(1)
    a.insert(0, 9)          # add at an index (shifts items) O(n)
    a.extend([7, 8])        # add many items at the end
    a.remove(9)             # remove the first match         O(n)
    last = a.pop()          # remove and return the last     O(1)
    a.sort()                # sort in place, stable          O(n log n)
    assert sorted(a, reverse=True)[0] == 7 and last == 8      # sorted() returns a NEW list
    assert a[1:3] == [2, 3] and a[::-1][0] == 7               # slicing is [start:stop:step]
    assert a.index(3) == 2 and a.count(1) == 1                # position of a value / how many times it appears
    matrix = [[0] * 3 for _ in range(2)]                      # right way: each row is a separate list
    matrix[0][0] = 1
    assert matrix[1][0] == 0                                  # [[0]*3]*2 would share one row (bug)


def tuples():
    """tuple: ordered, immutable, hashable (if its contents are). Use as dict keys or to return several values."""
    t = (1, 2, 3)
    x, *rest = t                                    # unpacking; *rest collects the remaining items
    assert x == 1 and rest == [2, 3]
    d = {(0, 0): "origin"}                          # a tuple can be a dict key (a list cannot)
    assert d[(0, 0)] == "origin"
    single = (5,)                                   # the comma makes the tuple, not the brackets
    assert isinstance(single, tuple)


def sets():
    """set: unordered, unique items, O(1) membership test. Items must be hashable."""
    a, b = {1, 2, 3}, {2, 3, 4}
    assert a | b == {1, 2, 3, 4}                    # union
    assert a & b == {2, 3}                          # intersection
    assert a - b == {1}                             # difference (in a, not in b)
    assert a ^ b == {1, 4}                          # symmetric difference (in exactly one)
    assert 2 in a                                   # O(1), a list would be O(n)
    assert list(dict.fromkeys([3, 1, 3, 2])) == [3, 1, 2]   # dedupe while keeping order
    fs = frozenset([1, 2])                          # immutable set, so it can be a dict key
    assert {fs: 1}[frozenset([2, 1])] == 1


def dicts():
    """dict: key -> value, keeps insertion order (3.7+), O(1) average lookup."""
    d = {"a": 1, "b": 2}
    d["c"] = 3                                      # add or overwrite
    assert d.get("z", 0) == 0                       # get() with a default avoids KeyError
    assert d.setdefault("d", []) == []              # insert the default if the key is missing, return the value
    d.pop("d")                                      # remove a key
    assert list(d.items())[0] == ("a", 1)           # items() gives (key, value) pairs
    merged = {**d, "a": 100} | {"e": 5}             # merge dicts (the | operator needs Python 3.9+)
    assert merged["a"] == 100 and merged["e"] == 5  # later values win
    inverted = {v: k for k, v in {"x": 1, "y": 2}.items()}   # dict comprehension: swap keys and values
    assert inverted == {1: "x", 2: "y"}
    assert sorted(d, key=d.get, reverse=True)[0] == "c"       # keys ordered by their value, highest first


def strings():
    """str: immutable sequence of characters. Build big strings with join, not repeated +=."""
    s = "  Hello, World  "
    assert s.strip().lower() == "hello, world"      # strip() removes surrounding spaces
    assert "a,b,c".split(",") == ["a", "b", "c"] and "-".join(["a", "b"]) == "a-b"   # split <-> join
    assert "abc".startswith("ab") and "abc".replace("b", "X") == "aXc"
    name, n = "Ann", 3
    assert f"{name} has {n:03d} items, {3.14159:.2f}" == "Ann has 003 items, 3.14"   # f-string: 03d pads, .2f rounds
    assert "racecar" == "racecar"[::-1]             # palindrome check: compare with the reversed string
    assert "hello"[1:3] == "el" and "hello".find("z") == -1   # find() returns -1 when missing (index() would raise)


def collections_module():
    """The collections types you should know by name."""
    # Counter: frequency map (count occurrences)
    c = Counter("abracadabra")
    assert c.most_common(1) == [("a", 5)]

    # defaultdict: creates a missing value automatically, perfect for grouping
    groups = defaultdict(list)
    for word in ["apple", "avocado", "banana"]:
        groups[word[0]].append(word)                # no need to check if the key exists
    assert groups["a"] == ["apple", "avocado"]

    # deque: O(1) at both ends (queues, sliding windows). list.pop(0) is O(n).
    q = deque([1, 2, 3], maxlen=3)
    q.append(4)                                     # with maxlen, the oldest item (1) is dropped
    assert list(q) == [2, 3, 4] and q.popleft() == 2

    # namedtuple: lightweight record with named fields
    Point = namedtuple("Point", "x y")
    p = Point(1, 2)
    assert p.x == 1 and p._asdict() == {"x": 1, "y": 2}

    # OrderedDict: ordered dict with move_to_end (building block of an LRU cache)
    od = OrderedDict(a=1, b=2)
    od.move_to_end("a")                             # "a" becomes the most recently used
    assert list(od) == ["b", "a"]

    # ChainMap: layered lookups (for example defaults <- config file <- command-line args)
    cm = ChainMap({"x": 1}, {"x": 0, "y": 2})       # the first mapping that has the key wins
    assert cm["x"] == 1 and cm["y"] == 2


def heaps_and_bisect():
    """heapq: min-heap (priority queue). bisect: binary search in a sorted list."""
    h = []
    for x in [5, 1, 4, 2]:
        heapq.heappush(h, x)                        # O(log n)
    assert heapq.heappop(h) == 1                    # always returns the smallest item
    assert heapq.nlargest(2, [5, 1, 4, 2]) == [5, 4]
    maxheap = [-x for x in [5, 1, 4]]               # max-heap trick: store negatives
    heapq.heapify(maxheap)                          # turn a list into a heap in O(n)
    assert -heapq.heappop(maxheap) == 5
    tasks = [(2, "b"), (1, "a")]                    # tuples compare by the first item, so it acts as the priority
    heapq.heapify(tasks)
    assert heapq.heappop(tasks) == (1, "a")

    sorted_list = [1, 3, 5, 7]
    assert bisect.bisect_left(sorted_list, 5) == 2  # index where 5 is (or would be inserted), O(log n)
    bisect.insort(sorted_list, 4)                   # insert and keep the list sorted
    assert sorted_list == [1, 3, 4, 5, 7]


@dataclass
class Ticket:
    """dataclass: auto-generates __init__, __repr__ and __eq__. Prefer it over hand-written boilerplate."""
    id: int
    title: str
    tags: list = field(default_factory=list)        # mutable defaults need default_factory (a fresh list per object)


def dataclass_demo():
    """Shows the methods a dataclass gives you for free."""
    t = Ticket(1, "disk full")
    assert t == Ticket(1, "disk full") and t.tags == []   # __eq__ compares all fields
    assert "Ticket(id=1" in repr(t)                       # __repr__ is generated


class Stack:
    """Stack (LIFO: last in, first out) using a list. Used for brackets, undo and DFS."""

    def __init__(self):
        """Start with an empty stack."""
        self._items = []

    def push(self, x):
        """Put x on top."""
        self._items.append(x)

    def pop(self):
        """Remove and return the top item."""
        return self._items.pop()

    def peek(self):
        """Look at the top item without removing it."""
        return self._items[-1]

    def __len__(self):
        """Number of items (makes len(stack) work)."""
        return len(self._items)


class Queue:
    """Queue (FIFO: first in, first out) using a deque. Used for BFS and task queues."""

    def __init__(self):
        """Start with an empty queue."""
        self._items = deque()

    def enqueue(self, x):
        """Add x at the back."""
        self._items.append(x)

    def dequeue(self):
        """Remove and return the front item (O(1) with deque)."""
        return self._items.popleft()


class Node:
    """Singly linked list node: a value and a pointer to the next node."""

    def __init__(self, val, next=None):
        """Create a node holding val that points to `next`."""
        self.val, self.next = val, next


def stack_queue_linkedlist():
    """Exercise Stack, Queue and a linked-list reversal."""
    s = Stack()
    s.push(1), s.push(2)
    assert s.pop() == 2 and len(s) == 1             # last in, first out
    q = Queue()
    q.enqueue("a"), q.enqueue("b")
    assert q.dequeue() == "a"                       # first in, first out
    head = Node(1, Node(2, Node(3)))                # 1 -> 2 -> 3
    prev = None
    while head:                                     # reverse in place: flip each pointer, walk forward
        head.next, prev, head = prev, head, head.next
    assert [prev.val, prev.next.val, prev.next.next.val] == [3, 2, 1]


def valid_brackets(s: str) -> bool:
    """Classic stack problem: are all brackets closed in the right order?

    Args:
        s: string containing brackets such as "{[()]}".
    Returns:
        True if every opener has a matching closer in the correct order.
    """
    pairs = {")": "(", "]": "[", "}": "{"}          # closer -> matching opener
    st = []
    for ch in s:
        if ch in pairs.values():
            st.append(ch)                           # opener: remember it
        elif ch in pairs:
            if not st or st.pop() != pairs[ch]:     # closer must match the latest opener
                return False
    return not st                                   # leftover openers mean unbalanced


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    for fn in (lists, tuples, sets, dicts, strings, collections_module, heaps_and_bisect,
               dataclass_demo, stack_queue_linkedlist):
        fn()
    assert valid_brackets("{[()]}") and not valid_brackets("(]")
    print("01 data structures: all checks passed")

# Big-O cheat sheet (average case):
#   list    : index O(1) | append O(1) | insert/remove/pop(0) O(n) | `in` O(n) | sort O(n log n)
#   dict/set: get/set/delete/`in` O(1)
#   deque   : append/pop at both ends O(1) | index in the middle O(n)
#   heapq   : push/pop O(log n) | peek heap[0] O(1) | heapify O(n)
#   bisect  : search O(log n) | insort O(n) because of the shift
