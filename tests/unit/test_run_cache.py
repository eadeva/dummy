from ptk.application.use_cases.run_cache import RunCache
from ptk.domain.logging import Level


class Store:
    def __init__(self):
        self.records, self.invalidated = {}, []

    def fingerprint(self, paths, cancel):
        return "digest"

    def read(self, identity):
        return self.records.get(identity)

    def write(self, identity, record):
        self.records[identity] = record

    def invalidate(self, identity):
        self.invalidated.append(identity)
        self.records.pop(identity, None)


class Never:
    def is_set(self):
        return False


def cache(store, logs, enabled=True):
    return RunCache(
        store,
        variant=None,
        job="build",
        run_id="r1",
        enabled=enabled,
        cancel=Never(),
        log=lambda level, text: logs.append((level, text)),
    )


def test_receipts_are_scoped_to_variant_and_job():
    store, logs = Store(), []
    runs = cache(store, logs)
    key = runs.key("cfg", {"producer": ["in"]})
    assert key
    runs.save("job", key, ["out"])
    assert set(store.records) == {"default:build:job"}
    assert runs.probe("job", key, ["out"]) == "r1"
    runs.invalidate("job")
    assert store.invalidated == ["default:build:job"] and not store.records


def test_disabled_cache_and_storage_failures_never_fail_the_run():
    store, logs = Store(), []
    assert cache(store, logs, enabled=False).key("cfg", {"p": ["in"]}) is None

    def broken(identity):
        raise OSError("disk full")

    store.read = broken
    runs = cache(store, logs)
    assert runs.probe("job", runs.key("cfg", {"p": ["in"]}), []) == ""
    assert logs and logs[0][0] is Level.WARNING and "disk full" in logs[0][1]
    runs.save("job", "key", [])
    assert not store.records
