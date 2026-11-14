"""Langfuse tracing for the agent. Off when any LANGFUSE_* key is missing; never breaks an answer."""
import contextlib
import functools
import logging
import os

log = logging.getLogger(__name__)
KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")


@functools.lru_cache(maxsize=1)
def _make(public_key: str, secret_key: str, host: str):
    from langfuse import Langfuse  # lazy: no import cost when tracing is off
    # timeout bounds each export request, so a dead Langfuse host costs seconds, not minutes.
    return Langfuse(public_key=public_key, secret_key=secret_key, base_url=host, timeout=5)


def _client():
    vals = [os.environ.get(k) for k in KEYS]
    if not all(vals):
        return None
    try:
        return _make(*vals)
    except Exception:
        log.warning("Langfuse client could not start; tracing off.", exc_info=True)
        return None


class Trace:
    """One trace per ask. Every method swallows tracing errors."""

    def __init__(self, question: str, model: str):
        self.root = None
        self._lf = _client()
        self._stack = contextlib.ExitStack()
        if self._lf is None:
            return
        try:
            from langfuse import propagate_attributes
            self.root = self._stack.enter_context(self._lf.start_as_current_observation(
                as_type="agent", name="ask", input=question, metadata={"model": model}))
            self._stack.enter_context(propagate_attributes(trace_name="ask", tags=[model], metadata={"model": model}))
        except Exception:
            log.warning("Tracing failed to start.", exc_info=True)
            self._close()

    @property
    def trace_id(self) -> str | None:
        return getattr(self.root, "trace_id", None)

    @contextlib.contextmanager
    def child(self, as_type: str, name: str, **start):
        """Observation around a block. The block fills the yielded dict with update() fields."""
        obs, rec = None, {}
        if self.root is not None:
            try:
                obs = self.root.start_observation(as_type=as_type, name=name, **start)
            except Exception:
                log.warning("Tracing failed.", exc_info=True)
        try:
            yield rec
        finally:
            if obs is not None:
                try:
                    obs.update(**rec)
                    obs.end()
                except Exception:
                    log.warning("Tracing failed.", exc_info=True)

    def end(self, answer: str | None) -> str | None:
        """Close the trace and flush (serverless freezes after the response). Returns the trace id or None."""
        tid = self.trace_id
        if self.root is None:
            return None
        try:
            self.root.update(output=answer)
        except Exception:
            log.warning("Tracing failed.", exc_info=True)
        self._close()
        try:
            self._lf.flush()
        except Exception:
            log.warning("Tracing flush failed.", exc_info=True)
        return tid if self.root is not None else None

    def _close(self):
        try:
            self._stack.close()
        except Exception:
            log.warning("Tracing failed to close.", exc_info=True)
            self.root = None


def score(trace_id: str | None, name: str, value: float | int | str, comment: str | None = None) -> None:
    if trace_id is None:
        return
    lf = _client()
    if lf is None:
        return
    try:
        lf.create_score(trace_id=trace_id, name=name, value=value, comment=comment)
        lf.flush()
    except Exception:
        log.warning("Langfuse score failed.", exc_info=True)
