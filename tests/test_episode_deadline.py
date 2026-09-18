"""Exercise the real model-call timer without contacting a model endpoint."""
import signal
import threading
import time

import pytest

from sle.episode_deadline import call_with_deadline


pytestmark = pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="POSIX timers required")


def test_total_timeout_escapes_transport_retry_and_restores_alarm():
    previous = signal.getsignal(signal.SIGALRM)
    retries = []

    def retrier():
        for _ in range(3):
            try:
                time.sleep(1)
            except Exception:
                retries.append(True)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        call_with_deadline(retrier, 0.05)
    assert time.monotonic() - started < 0.8
    assert retries == []
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_success_and_failure_restore_handler():
    previous = signal.getsignal(signal.SIGALRM)
    assert call_with_deadline(lambda: 17, 1) == 17
    with pytest.raises(ValueError):
        call_with_deadline(lambda: int("bad"), 1)
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_existing_alarm_is_not_replaced():
    calls = []
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        with pytest.raises(RuntimeError):
            call_with_deadline(lambda: calls.append(True), 1)
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 50
        assert calls == []
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def test_other_threads_fail_before_model_call():
    calls, failures = [], []

    def invoke():
        try:
            call_with_deadline(lambda: calls.append(True), 1)
        except RuntimeError:
            failures.append(True)
    thread = threading.Thread(target=invoke)
    thread.start()
    thread.join()
    assert calls == [] and failures == [True]


@pytest.mark.parametrize("seconds", [0, -1, True, float("nan"), float("inf"), 10 ** 1000])
def test_invalid_budgets_fail_before_call(seconds):
    with pytest.raises(ValueError):
        call_with_deadline(lambda: pytest.fail("must not call"), seconds)
