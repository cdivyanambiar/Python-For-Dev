"""07 - Exceptions, files, JSON/CSV, context managers, logging.

Run: python 07_exceptions_and_files.py
Each function demonstrates one topic and checks itself with assert.
"""
import csv
import json
import logging
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path


class DeviceError(Exception):
    """Custom exception: subclass Exception and keep useful data on it."""

    def __init__(self, device, message):
        """Build a readable message and remember which device failed."""
        super().__init__(f"{device}: {message}")
        self.device = device


def exceptions():
    """try / except / else / finally, chaining, suppress and assert."""
    def risky(x):
        """Divide 10 by x; return None on division by zero. `finally` always records an event."""
        try:
            return 10 / x                           # code that may fail
        except ZeroDivisionError:                   # catch SPECIFIC exceptions, never a bare `except:`
            return None
        else:                                       # runs only if no exception AND no return above (so not reached here)
            pass
        finally:                                    # always runs, even after return: use for cleanup
            events.append("finally")

    events = []
    assert risky(2) == 5 and risky(0) is None and events == ["finally", "finally"]

    try:
        int("abc")
    except (ValueError, TypeError) as e:            # catch several types at once
        assert "invalid literal" in str(e)

    try:
        try:
            {}["missing"]
        except KeyError as e:
            raise DeviceError("gw1", "lookup failed") from e   # chain: keep the original error as __cause__
    except DeviceError as e:
        assert e.device == "gw1" and isinstance(e.__cause__, KeyError)

    with suppress(FileNotFoundError):               # ignore one specific, expected error
        Path("does_not_exist.txt").read_text()

    try:
        assert 1 == 2, "assertions are for bugs, not input validation"
    except AssertionError:
        pass
    # raise: signal an error | a bare `raise` inside except: re-raise | EAFP (try it) is preferred over LBYL (check first)


def files_and_paths():
    """Read and write text files with pathlib, using a temporary folder that is cleaned up automatically."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)                            # pathlib: modern, cross-platform paths
        p = base / "notes.txt"                      # `/` joins path parts
        p.write_text("line1\nline2\n", encoding="utf-8")
        assert p.exists() and p.suffix == ".txt" and p.name == "notes.txt"

        with open(p, "a", encoding="utf-8") as f:   # "a" = append; `with` closes the file even on error
            f.write("line3\n")
        with open(p, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f]        # iterating a file reads it lazily, one line at a time
        assert lines == ["line1", "line2", "line3"]
        assert sorted(x.name for x in base.glob("*.txt")) == ["notes.txt"]   # find files by pattern


def json_and_csv():
    """Convert between Python objects and JSON text, and read/write CSV and JSON Lines."""
    data = {"device": "gw1", "tags": ["a", "b"], "temp": 21.5, "ok": True, "note": None}
    text = json.dumps(data, indent=2)               # dict -> JSON string
    assert json.loads(text) == data                 # JSON string -> dict (tuples come back as lists)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "d.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:   # newline="" avoids blank lines on Windows
            w = csv.DictWriter(f, fieldnames=["device", "bytes"])
            w.writeheader()
            w.writerows([{"device": "a", "bytes": 10}, {"device": "b", "bytes": 20}])
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))          # each row becomes a dict keyed by the header
        assert rows[1] == {"device": "b", "bytes": "20"}   # CSV values are always strings: convert yourself

        jl = Path(tmp) / "events.jsonl"             # JSON Lines: one JSON object per line (logs, streaming)
        jl.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        assert [json.loads(ln)["device"] for ln in jl.read_text().splitlines()] == ["a", "b"]


@contextmanager
def timer_ctx(store):
    """Context manager built from a generator: record start and end around a block."""
    store.append("start")
    try:
        yield                                       # the body of the with-statement runs here
    finally:
        store.append("end")                         # runs even if the body raised


def context_managers():
    """Use the context manager above and check the order of events."""
    store = []
    with timer_ctx(store):
        store.append("work")
    assert store == ["start", "work", "end"]


def logging_demo():
    """Use logging, not print, in real programs: levels, formatting and handlers."""
    logger = logging.getLogger("demo")
    logger.setLevel(logging.INFO)                   # DEBUG messages will be dropped
    records = []

    class ListHandler(logging.Handler):
        """Handler that stores records in a list instead of printing (handy for tests)."""

        def emit(self, record):
            """Called for every log record that passes the level filter."""
            records.append((record.levelname, record.getMessage()))

    logger.addHandler(ListHandler())
    logger.debug("hidden")                          # below INFO: dropped
    logger.info("device %s online", "gw1")          # lazy %-formatting: only built if the message is emitted
    logger.error("failed")
    assert records == [("INFO", "device gw1 online"), ("ERROR", "failed")]
    # levels: DEBUG < INFO < WARNING < ERROR < CRITICAL


if __name__ == "__main__":
    # run every demo; any failed assert stops the script with a message
    exceptions()
    files_and_paths()
    json_and_csv()
    context_managers()
    logging_demo()
    print("07 exceptions and files: all checks passed")
