import asyncio
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore, Lock

from utils.limits import MAX_ACTIVE_JOBS, MAX_WAITING_JOBS


class ProcessingPermit:
    def __init__(self, pool):
        self._pool = pool
        self._submitted = False
        self._released = False
        self._queued = False
        self._active = False
        self._turn = Future()

    async def wait_for_turn(self):
        with self._pool.lock:
            if self._queued or self._released:
                raise RuntimeError("Processing permit is no longer available")
            self._queued = True
            self._pool.waiting.append(self)
            self._pool.start_waiters()
        try:
            # Shield the cross-thread notification; cancellation removes the
            # actual queue entry below, not just its asyncio wrapper.
            await asyncio.shield(asyncio.wrap_future(self._turn))
        except BaseException:
            self.release_if_unused()
            raise

    def submit(self, function, *args):
        with self._pool.lock:
            if not self._active or self._submitted or self._released:
                raise RuntimeError("Processing permit is no longer available")
            future = self._pool.executor.submit(function, *args)
            self._submitted = True
        # A disconnected HTTP task must not free a still-running native job's slot.
        future.add_done_callback(lambda _: self.release())
        return future

    def release(self):
        with self._pool.lock:
            self._release_locked()

    def release_if_unused(self):
        with self._pool.lock:
            if not self._submitted:
                self._release_locked()

    def _release_locked(self):
        if self._released:
            return
        self._released = True
        if self._active:
            self._pool.active -= 1
        elif self._queued:
            self._pool.waiting.remove(self)
        self._turn.cancel()
        self._pool.slots.release()
        self._pool.start_waiters()


class ProcessingPool:
    def __init__(self, capacity=MAX_ACTIVE_JOBS, max_waiting=MAX_WAITING_JOBS):
        if capacity < 1 or max_waiting < 0:
            raise ValueError("Processing capacity must be positive and waiting capacity nonnegative")
        self.capacity = capacity
        self.slots = BoundedSemaphore(capacity + max_waiting)
        self.lock = Lock()
        self.active = 0
        self.waiting = deque()
        self.executor = ThreadPoolExecutor(
            max_workers=capacity, thread_name_prefix="passport-inference"
        )

    def start_waiters(self):
        """Called with lock held; never enqueue waiting work in the executor."""
        while self.active < self.capacity and self.waiting:
            permit = self.waiting.popleft()
            permit._active = True
            self.active += 1
            permit._turn.set_result(None)

    def try_acquire(self):
        if not self.slots.acquire(blocking=False):
            return None
        return ProcessingPermit(self)


# Bound uploads before parsing, then run validated photos in FIFO order.
# Only active work reaches the executor, so cancelled queue entries retain no jobs.
processing_pool = ProcessingPool()
