from datetime import datetime, timedelta, timezone

import pytest
import yaml

from ptk.application.use_cases.run import PrepareRun, RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.dates import date_values
from ptk.domain.errors import ConfigError
from tests.project_files import project_files

AT = datetime(2026, 10, 26, 0, 7, 8, tzinfo=timezone(timedelta(hours=1)))


def test_local_utc_and_custom_date_parts_share_one_instant():
    values = date_values(AT)
    assert values["timestamp"] == "2026_10_26_0007"
    assert values["timestamp_seconds"] == "2026_10_26_000708"
    assert values["utc"]["timestamp"] == "2026_10_25_2307"
    assert values["iso"] == "2026-10-26T00:07:08+01:00"
    assert f"{values['year']}-{values['month']}-{values['day']}" == "2026-10-26"
    with pytest.raises(ValueError, match="timezone-aware"):
        date_values(AT.replace(tzinfo=None))


def test_job_defaults_vars_environment_and_steps_freeze_the_clock(write, load):
    root = write(
        project_files("""
project: {name: demo}
vars: {folder: "out/${date.timestamp}"}
environment: {set: {GLOBAL_DATE: "${date.utc.timestamp}"}}
jobs:
  build:
    params: {stamp: {default: "${date.timestamp}"}}
    env: {JOB_DATE: "${date.timestamp}"}
    steps:
      - first: {uses: echo, with: {message: "${vars.folder}/${params.stamp}"}}
      - second: {uses: echo, with: {message: "${date.timestamp}/${date.utc.timestamp}"}, env: {STEP_DATE: "${date.iso}"}}
""")
    )
    app = create_app(started_at=AT)
    project = load(root)
    instants = iter([AT, AT + timedelta(minutes=1)])
    prepare = PrepareRun(app.host, clock=lambda: next(instants))
    plan = prepare.execute(project, RunRequest(job="build", dry_run=True)).plan
    assert plan.params["stamp"] == "2026_10_26_0007"
    assert plan.base_env["GLOBAL_DATE"] == "2026_10_25_2307"
    assert plan.base_env["JOB_DATE"] == "2026_10_26_0007"
    assert plan.steps[0].with_["message"] == "out/2026_10_26_0007/2026_10_26_0007"
    assert plan.steps[1].with_["message"] == "2026_10_26_0007/2026_10_25_2307"
    assert plan.steps[1].env["STEP_DATE"] == AT.isoformat()
    assert plan.report_context["date"]["iso"] == AT.isoformat()
    assert next(instants) == AT + timedelta(minutes=1)
    for _ in range(2):
        prepared = app.prepare_run(project).execute(
            project, RunRequest(job="build", dry_run=True)
        )
        assert prepared.plan.params["stamp"] == plan.params["stamp"]


@pytest.mark.parametrize("field", ["timestmp", "utc.unknown", "utc.utc.timestamp"])
def test_unknown_date_fields_fail_configuration_validation(write, load, field):
    root = write(
        project_files(
            yaml.safe_dump(
                {
                    "project": {"name": "demo"},
                    "vars": {"stamp": "${date." + field + "}"},
                }
            )
        )
    )
    with pytest.raises(ConfigError, match="unknown date field"):
        load(root)
