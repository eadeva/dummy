"""CMake 3.2 <= version < 4.1: explicit capability gates, no version guessing."""

from .common import (
    attempt,
    read_api,
    read_cache,
    read_events,
    read_legacy_checks,
    stamp,
)


class CMake32Importer:
    name = "cmake-3.2"

    def collect(self, report, build, before, version, problems):
        cache = build / "CMakeCache.txt"
        if cache.is_file() and (
            report.status == "passed" or before.get(str(cache)) != stamp(cache)
        ):
            attempt(
                report, problems, "configuration", lambda: read_cache(report, build)
            )
        log = None
        if version >= (3, 20, 0):
            # 3.20 supplies all codemodel/cache/toolchains versions requested by PTK.
            try:
                log = read_api(report, build, before, problems)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                problems.append(f"{report.step}: cannot import CMake File API: {exc}")
        else:
            report.availability["targets"] = "PTK File API capture requires CMake 3.20+"
        if version >= (3, 26, 0):
            attempt(
                report,
                problems,
                "checks",
                lambda: read_events(report, build, before, log),
            )
        else:
            attempt(
                report,
                problems,
                "checks",
                lambda: read_legacy_checks(report, build, before),
            )
        report.availability["packages"] = (
            "Structured package discovery requires CMake 4.1+"
        )
