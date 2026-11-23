"""10 - Concurrency: threads, processes, asyncio, and the GIL.

Rule of thumb:
  I/O-bound (network, disk, APIs)  -> threads or asyncio
  CPU-bound (maths, parsing, ML)   -> multiprocessing (or numpy / native code)
The GIL (Global Interpreter Lock) lets only one thread run Python bytecode at a time,
so threads don't speed up CPU-bound pure-Python code, but they do help while waiting on I/O.

Run: python 10_concurrency.py
"""
import asyncio
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed


def fake_io(n):
    """Pretend to call a slow network service, then return n doubled."""
    time.sleep(0.2)
    return n * 2


def cpu_work(n):
    """CPU-heavy work: sum of squares below n."""
    return sum(i * i for i in range(n))


def basic_thread_demo():
    """2-minute demo: start() begins a thread, join() waits for it. Three 0.2 s calls overlap."""
    results = {}

    def download(name):
        """Pretend API call; while it sleeps, the other threads run."""
        time.sleep(0.2)
        results[name] = f"{name} done"

    ts = [threading.Thread(target=download, args=(n,)) for n in ("a", "b", "c")]
    start = time.perf_counter()
    for t in ts:
        t.start()                                                        # begin running in the background
    for t in ts:
        t.join()                                                         # wait until this thread finishes
    assert len(results) == 3 and time.perf_counter() - start < 0.5       # ~0.2 s, not 0.6 s


def threads():
    """A thread pool overlaps waiting time: 5 calls of 0.2 s finish in about 0.2 s, not 1.0 s."""
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as pool:                      # 5 worker threads
        results = list(pool.map(fake_io, range(5)))                      # results come back in input order
    elapsed = time.perf_counter() - start
    assert results == [0, 2, 4, 6, 8] and elapsed < 0.8                  # ~0.2 s, not 1.0 s sequentially

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fake_io, i): i for i in range(3)}         # submit returns a Future immediately
        done = {futures[f]: f.result() for f in as_completed(futures)}   # handle results as each one finishes
    assert done == {0: 0, 1: 2, 2: 4}


def race_condition_and_lock():
    """Four threads increment one counter; the lock prevents lost updates."""
    counter = {"n": 0}
    lock = threading.Lock()

    def work():
        """Increment the shared counter 10,000 times."""
        for _ in range(10_000):
            with lock:                                                   # only one thread at a time in this block
                counter["n"] += 1                                        # read-modify-write is NOT atomic without the lock

    ts = [threading.Thread(target=work) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()                                                         # wait for the thread to finish
    assert counter["n"] == 40_000


def processes():
    """Separate processes each have their own GIL, so CPU-bound work really runs in parallel."""
    with ProcessPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(cpu_work, [10, 100])) == [285, 328350]


async def fetch(n):
    """Async 'network call'. `await` hands control back to the event loop while waiting."""
    await asyncio.sleep(0.2)
    return n * 2


async def main_async():
    """Run many async tasks on ONE thread, with a concurrency limit and a timeout."""
    start = time.perf_counter()
    results = await asyncio.gather(*(fetch(i) for i in range(5)))        # all 5 run concurrently
    assert results == [0, 2, 4, 6, 8] and time.perf_counter() - start < 0.8

    sem = asyncio.Semaphore(2)                                           # at most 2 at a time (rate limiting)

    async def limited(n):
        """fetch(n) but only when a semaphore slot is free."""
        async with sem:
            return await fetch(n)
    assert await asyncio.gather(*(limited(i) for i in range(4))) == [0, 2, 4, 6]

    try:
        await asyncio.wait_for(asyncio.sleep(1), timeout=0.05)           # cancel work that takes too long
    except asyncio.TimeoutError:
        pass


def producer_consumer():
    """Classic pattern: one thread produces work, another consumes it through a thread-safe queue."""
    import queue
    q = queue.Queue()                                                    # thread-safe queue
    out = []

    def consumer():
        """Take items until the None stop signal arrives."""
        while (item := q.get()) is not None:                             # None = stop signal
            out.append(item * 2)

    t = threading.Thread(target=consumer)
    t.start()
    for i in range(3):
        q.put(i)                                                         # producer side
    q.put(None)                                                          # tell the consumer to stop
    t.join()
    assert out == [0, 2, 4]


if __name__ == "__main__":                                               # guard is required for multiprocessing on Windows
    # run every demo; any failed assert stops the script with a message
    basic_thread_demo()
    threads()
    race_condition_and_lock()
    processes()
    asyncio.run(main_async())                                            # start the event loop and run the async demo
    producer_consumer()
    print("10 concurrency: all checks passed")

# 2-MINUTE SCRIPT: THREADING
#  1. What: a thread is a lightweight worker inside one process; threads share memory.
#  2. Why: while one thread waits on network/disk/API, another runs -> good for I/O-bound work.
#  3. Demo (basic_thread_demo): three 0.2 s calls finish in ~0.2 s. start() begins, join() waits.
#  4. GIL: only one thread runs Python bytecode at a time, so no speed-up for CPU-bound code -> multiprocessing.
#  5. Risk: shared data + threads = race condition (counter += 1 is read, add, write). Fix with a Lock
#     (race_condition_and_lock ends at exactly 40,000).
#  6. Choosing: threads for a few I/O tasks, asyncio for thousands, processes for CPU work.
#  Follow-up: "Does threading give parallelism in Python?" Not for CPU-bound code, because of the GIL.
#
# Interview talking points:
#  - Concurrency (interleaving tasks) vs parallelism (running simultaneously).
#  - threads: shared memory, need locks; asyncio: single thread, cooperative, great for thousands of I/O calls;
#    processes: true parallelism, higher start-up and data-copy cost.
#  - Python 3.13 has an experimental free-threaded build with no GIL.
