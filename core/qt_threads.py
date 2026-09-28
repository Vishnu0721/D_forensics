"""Safe QThread shutdown.

QThread.terminate() kills a thread wherever it is, including in the middle of
Python code or a blocking DNS lookup, which crashes the process on exit.
Destroying a QThread that is still running aborts the process too. So threads
are asked to stop, and any that overrun are waited for just before exit.
"""
import atexit

_overrunning = []


def stop_qthread(thread, timeout_ms: int = 2000) -> bool:
    if thread is None:
        return True
    thread.requestInterruption()
    thread.quit()
    if thread.wait(timeout_ms):
        return True
    _overrunning.append(thread)
    return False


@atexit.register
def _wait_for_overrunning_threads():
    for thread in _overrunning:
        thread.wait()
    _overrunning.clear()
