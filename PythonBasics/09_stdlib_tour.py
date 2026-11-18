"""09 - Standard library you will actually use: re, datetime, math/statistics, random, os/sys, argparse, hashlib.

Run: python 09_stdlib_tour.py
Each function demonstrates one module and checks itself with assert.
"""
import argparse
import hashlib
import math
import os
import random
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone


def regex():
    """Regular expressions: search, findall, sub, split, fullmatch, compile, flags, greedy vs lazy."""
    log = "2026-03-01T10:00:01Z ERROR svc=auth user=123 msg=timeout after 30s"
    m = re.search(r"(?P<level>[A-Z]+) svc=(?P<svc>\w+)", log)            # (?P<name>...) = named group
    assert m["level"] == "ERROR" and m.group("svc") == "auth"
    assert re.findall(r"\d+", "a1 b22 c333") == ["1", "22", "333"]       # all non-overlapping matches
    assert re.sub(r"\d+", "<N>", "timeout after 30s") == "timeout after <N>s"   # replace matches
    assert re.split(r"[,;]\s*", "a, b;c") == ["a", "b", "c"]             # split on a pattern
    assert re.fullmatch(r"\d{3}-\d{4}", "555-1234") is not None          # the WHOLE string must match
    pat = re.compile(r"^(\S+) (\w+)")                                    # compile once, reuse in loops (faster)
    assert pat.match(log).group(2) == "ERROR"
    assert re.search(r"error", "An ERROR", re.IGNORECASE) is not None    # flags change behaviour
    assert re.search(r"a.*?b", "aXbYb").group() == "aXb"                 # `.*?` is lazy (shortest); `.*` is greedy (longest)
    # match anchors at the start, search looks anywhere, fullmatch needs the whole string


def dates_and_times():
    """datetime: create, shift, format, parse and subtract. Prefer timezone-aware UTC."""
    t = datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc)
    assert (t + timedelta(hours=2)).hour == 12                           # add a duration
    assert t.strftime("%Y-%m-%d %H:%M") == "2026-03-01 10:30"            # object -> text
    assert datetime.strptime("2026-03-01", "%Y-%m-%d").month == 3        # text -> object
    assert datetime.fromisoformat("2026-03-01T10:30:00+00:00") == t      # parse ISO 8601 text
    assert (t - datetime(2026, 3, 1, tzinfo=timezone.utc)).total_seconds() == 37800   # difference is a timedelta
    assert t.isoformat() == "2026-03-01T10:30:00+00:00"
    assert t.replace(minute=0, second=0) == datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)   # truncate to the hour


def numbers():
    """statistics, math, random and decimal, including the floating-point trap."""
    xs = [2, 4, 4, 4, 5, 5, 7, 9]
    assert statistics.mean(xs) == 5 and statistics.median(xs) == 4.5 and statistics.mode(xs) == 4
    assert round(statistics.pstdev(xs), 2) == 2.0                        # population std; stdev() is the sample std
    assert math.sqrt(16) == 4 and math.isclose(0.1 + 0.2, 0.3) and 0.1 + 0.2 != 0.3   # never compare floats with ==
    assert math.ceil(2.1) == 3 and math.floor(-2.1) == -3 and math.gcd(12, 18) == 6 and math.inf > 10**100
    assert math.log(math.e) == 1 and math.comb(5, 2) == 10               # comb = "n choose k"
    random.seed(0)                                                       # fixed seed = repeatable "random" numbers
    assert 0 <= random.random() < 1 and random.choice("abc") in "abc"
    assert len(random.sample(range(10), 3)) == 3                         # 3 distinct picks
    from decimal import Decimal                                          # exact decimal arithmetic (money)
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")


def system_and_args():
    """os, sys and argparse: paths, environment variables and command-line arguments."""
    assert os.path.basename("/a/b/c.txt") == "c.txt" and os.path.splitext("c.txt")[1] == ".txt"
    assert isinstance(sys.argv, list) and sys.version_info >= (3, 8)     # argv = the command-line arguments
    os.environ["DEMO_VAR"] = "1"
    assert os.getenv("DEMO_VAR") == "1" and os.getenv("MISSING", "dflt") == "dflt"   # configuration via environment variables
    parser = argparse.ArgumentParser(description="demo")
    parser.add_argument("path")                                          # required positional argument
    parser.add_argument("--limit", type=int, default=10)                 # optional, converted to int
    parser.add_argument("-v", "--verbose", action="store_true")          # flag: True when present
    args = parser.parse_args(["data.csv", "--limit", "5", "-v"])         # normally parse_args() reads sys.argv
    assert (args.path, args.limit, args.verbose) == ("data.csv", 5, True)


def hashing_and_ids():
    """hashlib, uuid, base64 and secrets."""
    assert hashlib.sha256(b"abc").hexdigest().startswith("ba7816bf")     # fingerprints, dedupe, checksums
    import uuid
    assert len(str(uuid.uuid4())) == 36                                  # random unique id
    import base64
    assert base64.b64decode(base64.b64encode(b"hi")) == b"hi"            # encoding, NOT encryption
    import secrets                                                       # use secrets (not random) for tokens and passwords
    assert len(secrets.token_hex(8)) == 16


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    regex()
    dates_and_times()
    numbers()
    system_and_args()
    hashing_and_ids()
    print("09 stdlib tour: all checks passed")
