"""Bound one trusted model call, including retries and streaming, on POSIX.

This wrapper is for the standalone operator CLI, never for candidate code. A
BaseException escapes transport retry handlers before becoming TimeoutError.
"""
import math
import signal
import threading


class _DeadlineExpired(BaseException):
    pass


def call_with_deadline(callback, seconds):
    try:
        valid = not isinstance(seconds, bool) and math.isfinite(seconds) and seconds > 0
    except (TypeError, OverflowError):
        valid = False
    if not valid:
        raise ValueError("model deadline must be positive and finite")
    if (threading.current_thread() is not threading.main_thread()
            or not all(hasattr(signal, name) for name in
                       ("SIGALRM", "ITIMER_REAL", "setitimer", "getitimer"))):
        raise RuntimeError("bounded episode transport requires a POSIX main thread")
    if any(signal.getitimer(signal.ITIMER_REAL)):
        raise RuntimeError("episode transport cannot replace an existing alarm")
    previous = signal.getsignal(signal.SIGALRM)

    def expire(_signum, _frame):
        raise _DeadlineExpired()

    signal.signal(signal.SIGALRM, expire)
    try:
        signal.setitimer(signal.ITIMER_REAL, float(seconds))
        try:
            return callback()
        except _DeadlineExpired:
            raise TimeoutError("episode model call exceeded remaining wall budget") from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
