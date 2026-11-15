import threading


class Cancelled(Exception):
    """Raised when the user cancels an invoice check."""


_events: dict[str, threading.Event] = {}
_lock = threading.Lock()


def register(job_id):
    if not job_id:
        return
    with _lock:
        _events.setdefault(job_id, threading.Event())


def request_cancel(job_id):
    with _lock:
        _events.setdefault(job_id, threading.Event()).set()


def is_cancelled(job_id) -> bool:
    if not job_id:
        return False
    ev = _events.get(job_id)
    return bool(ev and ev.is_set())


def check(job_id):
    if is_cancelled(job_id):
        raise Cancelled()


def cleanup(job_id):
    if job_id:
        with _lock:
            _events.pop(job_id, None)