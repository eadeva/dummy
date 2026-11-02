"""Output-cache receipts for one job run (keys, probes and saves)."""

from __future__ import annotations

from collections.abc import Callable

from ...domain.logging import Level
from ..ports import CancelToken, OutputCache


class RunCache:
    """Never fails a run: storage problems disable caching for the rest of it."""

    def __init__(
        self,
        store: OutputCache | None,
        *,
        variant: str | None,
        job: str,
        run_id: str,
        enabled: bool,
        cancel: CancelToken,
        log: Callable[[Level, str], None],
    ):
        self._store = store
        self._prefix = f"{variant or 'default'}:{job}:"
        self._run_id = run_id
        self._available = store is not None and enabled
        self._cancel = cancel
        self._log = log

    def key(self, configuration, dependencies, *, skip_ptk_cache: bool = False):
        if not self._available or skip_ptk_cache:
            return None
        from ...domain.execution.cache import input_key

        return input_key(
            configuration,
            {
                name: self._store.fingerprint(paths, self._cancel) if paths else None
                for name, paths in dependencies.items()
            },
        )

    def probe(self, identity: str, key, outputs) -> str:
        """Return the run ID whose outputs can be reused, or an empty string."""
        if not self._available:
            return ""
        from ...domain.execution.cache import matches

        try:
            record = self._store.read(self._prefix + identity) if key else None
            if record and matches(
                record, key, self._store.fingerprint(outputs, self._cancel)
            ):
                return record["run_id"]
            # A new attempt invalidates its previous receipt, including forced
            # runs. Failed attempts cannot fall back to an older successful run.
            self.invalidate(identity)
        except OSError as exc:
            self._disable(f"PTK cache unavailable; executing normally: {exc}")
        return ""

    def invalidate(self, identity: str) -> None:
        if self._available:
            self._store.invalidate(self._prefix + identity)

    def save(self, identity: str, key, outputs) -> None:
        if not key or not self._available or self._cancel.is_set():
            return
        digest = self._store.fingerprint(outputs, self._cancel)
        if digest is None:
            return
        try:
            self._store.write(
                self._prefix + identity,
                {
                    "version": 1,
                    "inputs": key,
                    "outputs": digest,
                    "run_id": self._run_id,
                },
            )
        except OSError as exc:
            self._disable(f"PTK cache receipt not written: {exc}")

    def _disable(self, message: str) -> None:
        self._available = False
        self._log(Level.WARNING, message)
