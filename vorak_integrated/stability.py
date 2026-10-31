"""Bounded, cancellable utilities for VORAK's Windows Gemini Live console.

No OS permissions are granted here. Trusted owner confirmation remains mandatory.
"""
from __future__ import annotations
import asyncio
import queue
import signal
import sys
import threading
import time

SHUTDOWN = threading.Event()


def owner_confirmation(message: str, timeout_seconds: float = 25.0, *, key_source=None) -> bool:
    """Explicit physical YES in terminal; finite wait, Ctrl+C-aware.

    Unlike input() in asyncio.to_thread, no immortal executor thread is created.
    Never takes model-generated approval.
    """
    print('\nOWNER CONFIRMATION REQUIRED:', str(message)[:200], flush=True)
    print(f'Type YES then Enter within {int(timeout_seconds)} seconds to approve: ', end='', flush=True)
    if key_source is None:
        if sys.platform != 'win32':
            print('\nConfirmation unavailable outside Windows console; denied.', flush=True)
            return False
        import msvcrt
        key_source = lambda: msvcrt.getwch() if msvcrt.kbhit() else None
    letters = []
    limit = time.monotonic() + timeout_seconds
    while time.monotonic() < limit and not SHUTDOWN.is_set():
        key = key_source()
        if key is None:
            time.sleep(0.04)
            continue
        if key in ('\x03', '\x1b'):
            if key == '\x03': SHUTDOWN.set()
            print('\nConfirmation cancelled.', flush=True)
            return False
        if key in ('\r', '\n'):
            value = ''.join(letters) == 'YES'
            print('\nApproved.' if value else '\nDenied.', flush=True)
            return value and not SHUTDOWN.is_set()
        if key in ('\b', '\x7f'):
            if letters:
                letters.pop()
                print('\b \b', end='', flush=True)
        elif key.isprintable() and len(letters) < 12:
            letters.append(key)
            print('*', end='', flush=True)
    print('\nConfirmation timed out or shutdown requested; denied.', flush=True)
    return False


async def bounded_daemon_call(func, *args, timeout: float = 20.0, **kwargs):
    """Run potentially blocking OS/UI call on a daemon, not asyncio executor.

    Timeout reports an *unknown* outcome, not failure or success: the OS call
    might finish after our deadline. Never issue another action based on it.
    """
    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    def worker():
        try:
            result, error = func(*args, **kwargs), None
        except Exception as exc:
            result, error = None, exc
        try:
            def deliver():
                if not fut.done():
                    fut.set_exception(error) if error else fut.set_result(result)
            loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            pass  # event loop already closed after shutdown
    threading.Thread(target=worker, name='vorak-bounded-action', daemon=True).start()
    try:
        return await asyncio.wait_for(fut, timeout=timeout)
    except asyncio.TimeoutError:
        return {'status': 'unknown', 'message': 'Operation timed out; outcome not verified. Do not repeat automatically.'}


class AudioSink:
    """Daemon playback worker; never blocks asyncio.run executor shutdown.

    Receives PCM16 at 24 kHz. A single worker serializes writes. Queue is bounded.
    """
    def __init__(self, sounddevice, device=None):
        self.sd = sounddevice
        self.device = device
        self.q = queue.Queue(maxsize=256)  # VORAK_VOICE_STABILITY_AUDIO_BUFFER_V3: reduce lost speech bursts
        self.stop = threading.Event()
        self.error = None
        self.dropped = 0
        self.thread = threading.Thread(target=self._worker, name='vorak-audio-output', daemon=True)

    def start(self):
        self.thread.start()

    def _worker(self):
        try:
            with self.sd.RawOutputStream(samplerate=24000, channels=1, dtype='int16', device=self.device) as stream:
                while not self.stop.is_set():
                    try: pcm = self.q.get(timeout=0.15)
                    except queue.Empty: continue
                    try:
                        if pcm is None: break
                        stream.write(pcm)
                    finally:
                        self.q.task_done()
        except Exception as exc:
            self.error = type(exc).__name__

    def write(self, pcm: bytes):
        if not self.stop.is_set():
            try: self.q.put_nowait(pcm)
            except queue.Full:
                self.dropped += 1
                # Prevent uncontrolled memory growth; no success claim if audio dropped.

    async def drain(self, max_wait: float = 6.0):
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline and self.q.unfinished_tasks and not SHUTDOWN.is_set() and self.error is None:
            await asyncio.sleep(0.035)
        if self.error:
            print('VOICE AUDIO ERROR:', self.error, flush=True)
        if self.dropped or self.q.unfinished_tasks:
            print('VOICE AUDIO WARNING: Some speech may have been lost or truncated.', flush=True)

    def abort(self):
        """Interrupt audible playback; drop remaining queued audio immediately.

        The currently writing PCM chunk may finish, but no subsequent chunks
        should play. This cannot interrupt a remote OS or network operation.
        """
        self.stop.set()
        while True:
            try:
                self.q.get_nowait()
                self.q.task_done()
            except queue.Empty:
                break
        if self.thread.is_alive():
            self.thread.join(timeout=0.12)

    def close(self):
        self.stop.set()
        try: self.q.put_nowait(None)
        except queue.Full: pass
        self.thread.join(timeout=0.6)  # daemon will never hold the process open


def run_interruptibly(coroutine):
    """Windows Ctrl+C sets shutdown flag and cancels the main asyncio task."""
    SHUTDOWN.clear()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(coroutine)
    old = signal.getsignal(signal.SIGINT)

    def stop_handler(_sig, _frame):
        SHUTDOWN.set()
        if not task.done():
            loop.call_soon_threadsafe(task.cancel)

    signal.signal(signal.SIGINT, stop_handler)
    try:
        try:
            return loop.run_until_complete(task)
        except asyncio.CancelledError:
            print('\nStopped by Ctrl+C.', flush=True)
        finally:
            SHUTDOWN.set()
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for t in pending: t.cancel()
            if pending:
                # Never wait forever for a websocket/audio coroutine during shutdown.
                loop.run_until_complete(asyncio.wait(pending, timeout=2.0))
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        signal.signal(signal.SIGINT, old)
        asyncio.set_event_loop(None)
        loop.close()
