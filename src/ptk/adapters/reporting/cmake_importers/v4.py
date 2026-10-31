"""CMake >= 4.1: structured configure events, including package discovery."""

from .common import attempt, read_api, read_cache, read_events, stamp


class CMake41Importer:
    name = "cmake-4.1"

    def collect(self, report, build, before, version, problems):
        cache = build / "CMakeCache.txt"
        if cache.is_file() and (
            report.status == "passed" or before.get(str(cache)) != stamp(cache)
        ):
            attempt(
                report, problems, "configuration", lambda: read_cache(report, build)
            )
        logs = []
        attempt(
            report,
            problems,
            "File API",
            lambda: logs.append(read_api(report, build, before, problems)),
        )
        log = logs[0] if logs else None
        if log:
            attempt(
                report,
                problems,
                "checks",
                lambda: read_events(report, build, before, log, packages=True),
            )
        else:
            report.availability["checks"] = "No current configureLog reply"
            report.availability["packages"] = "No current configureLog reply"
