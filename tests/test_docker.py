from types import SimpleNamespace

import pytest

from ptk.adapters.docker import DockerEngine
from ptk.domain.errors import ConfigError, PtkError
from ptk.drivers.cli import docker as docker_cli
from ptk.drivers.cli.main import cli
from ptk.drivers.cli.state import CliState
from tests.cli_runner import CliRunner
from tests.project_files import project_files

PROJECT = """
project: {name: demo}
docker:
  image: registry.example.com/team/build:1.0
  env: {http_proxy: "http://host.docker.internal:3128"}
  keep: [NO_PROXY]
jobs:
  build:
    params:
      jobs: {type: int, default: 2}
    outputs: [_bin/out.hex, _builds/inputs]
    steps:
      compile: {run: make all, secrets: {TOKEN: artifactory.token}}
  gui:
    gui: true
    steps:
      open: {run: tool}
  host-only:
    docker: false
    steps:
      run: {run: tool}
credentials:
  artifactory: {fields: [user, token], user_field: user}
"""


class Recorder:
    """subprocess.run stand-in: records argv/env/stdin and answers docker queries."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        for prefix, (code, out) in self.answers.items():
            if " ".join(argv).find(prefix) >= 0:
                return SimpleNamespace(returncode=code, stdout=out, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def commands(self):
        return [" ".join(argv) for argv, _ in self.calls]


def test_windows_engine_runs_docker_in_wsl_and_forwards_secret_names():
    run = Recorder()
    engine = DockerEngine(windows=True, distro="Ubuntu-24.04", run=run, environ={})
    engine.exec(
        "c", ["ptk", "run", "build"], workdir="/workspace", values={"TOKEN": "s3cret"}
    )
    argv, kwargs = run.calls[-1]
    assert argv[:5] == ["wsl", "-d", "Ubuntu-24.04", "--exec", "docker"]
    assert argv[argv.index("-e") : argv.index("-e") + 2] == ["-e", "TOKEN"]
    assert "s3cret" not in " ".join(argv)
    assert kwargs["env"]["TOKEN"] == "s3cret"
    assert kwargs["env"]["WSLENV"] == "TOKEN"


def test_jobs_run_in_docker_skip_the_host_tool_check(write, load):
    from ptk.application.use_cases.run import RunRequest
    from ptk.bootstrap import create_app

    model = PROJECT.replace(
        "jobs:\n  build:\n",
        "tools:\n  absent: {check: ptk-test-absent-tool --version}\n"
        "jobs:\n  build:\n    requires_tools: [absent]\n",
    ).replace(", secrets: {TOKEN: artifactory.token}", "")
    root = write(project_files(model))
    app = create_app(environ={"PTK_CX": "0"})
    project = app.load_project.execute(root)
    with pytest.raises(PtkError, match="missing or too old"):
        app.prepare_run(project).execute(project, RunRequest(job="build"))
    app.prepare_run(project).execute(
        project, RunRequest(job="build", check_tools=False)
    )


def test_container_user_gets_a_passwd_entry_without_shell_interpolation():
    run = Recorder()
    engine = DockerEngine(windows=False, distro="unused", run=run, environ={})
    engine.ensure_user("c", "1001:1001", "/workspace/.ptk/home")
    argv = run.calls[-1][0]
    assert argv[:5] == ["docker", "exec", "-u", "0", "c"]
    assert argv[-4:] == ["sh", "1001", "1001", "/workspace/.ptk/home"]


def test_linux_engine_calls_docker_directly_and_logs_in_with_stdin():
    run = Recorder()
    engine = DockerEngine(windows=False, distro="unused", run=run, environ={})
    engine.login("registry.example.com", "me", "s3cret")
    argv, kwargs = run.calls[-1]
    assert argv == [
        "docker",
        "login",
        "registry.example.com",
        "-u",
        "me",
        "--password-stdin",
    ]
    assert kwargs["input"] == "s3cret"


def test_missing_wsl_distribution_explains_the_installation():
    run = Recorder({"-l -q": (0, "Ubuntu\r\n".encode("utf-16-le"))})
    engine = DockerEngine(windows=True, distro="Ubuntu-24.04", run=run, environ={})
    with pytest.raises(PtkError, match="wsl --install -d Ubuntu-24.04"):
        engine.check()


def test_container_command_line_for_a_job():
    argv = docker_cli.container_argv(
        job="build",
        maintainer=False,
        variant="cgw_cs",
        params={"jobs": 4, "fast": True, "names": ["a", "b"]},
        features={"x.y": "1"},
        only_step="compile",
        args_for={"compile": ["-k", "a b"]},
        passthrough=["--extra"],
        overrides=["jobs.build.max_workers=2"],
        verbose=1,
        re_run=True,
    )
    assert argv == [
        "ptk", "-v", "-s", "jobs.build.max_workers=2", "-V", "cgw_cs", "-rr",
        "run", "build", "-p", "jobs=4", "-p", "fast=true", "-p", "names=a,b",
        "--feature", "x.y=1", "--only-step", "compile",
        "--args-for", "compile=-k 'a b'", "--", "--extra",
    ]  # fmt: skip
    assert docker_cli.container_argv(job="image", maintainer=True)[:3] == [
        "ptk",
        "maintainer",
        "run",
    ]


def test_docker_credential_must_exist(write, load):
    bad = PROJECT.replace(
        "  keep: [NO_PROXY]", "  keep: [NO_PROXY]\n  credential: missing"
    )
    with pytest.raises(ConfigError, match="docker.credential 'missing'"):
        load(write(project_files(bad)))


@pytest.mark.parametrize(
    ("os_name", "in_container", "flag", "expected"),
    [
        ("linux", False, None, True),
        ("windows", False, None, False),
        ("linux", True, None, False),
        ("windows", False, True, True),
        ("linux", False, False, False),
    ],
)
def test_docker_default_is_on_for_linux_only(
    write, load, os_name, in_container, flag, expected
):
    project = load(write(project_files(PROJECT)))
    host = SimpleNamespace(os_name=lambda: os_name, is_docker=lambda: in_container)
    state = CliState(app=SimpleNamespace(host=host), docker=flag)
    assert state.use_docker(project) is expected


class FakeEngine:
    def __init__(self, windows=True):
        self.windows = windows
        self.distro = "Ubuntu-24.04"
        self.calls = []
        self.state = None
        self.processes_running = 2

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return {
                "pull": True,
                "image_id": "sha256:abc",
                "path": "/mnt/c/repo",
                "home": "/home/me",
                "user": "1000:1000",
                "container": self.state,
                "processes": self.processes_running,
                "exec": 0,
                "rsync": 0,
            }.get(name)

        return record

    def names(self):
        return [name for name, _, _ in self.calls]


def _run(write, load, engine, environ=None):
    project = load(write(project_files(PROJECT)))
    host = SimpleNamespace(
        os_name=lambda: "windows" if engine.windows else "linux",
        variables=environ or {"NO_PROXY": "localhost"},
        user_id=lambda: "ade7pl",
    )
    state = SimpleNamespace(app=SimpleNamespace(host=host))
    lines = []
    return docker_cli.DockerRun(state, project, engine, out=lines.append), project


def test_windows_sync_mirrors_runs_and_copies_results_back(write, load, capsys):
    engine = FakeEngine()
    run, project = _run(write, load, engine)
    code = run.run(["ptk", "run", "build"], secrets={"TOKEN": "s3cret"}, cx=False)
    assert code == 0
    mirror = next(c for c in engine.calls if c[0] == "rsync")
    assert "--copy-unsafe-links" in mirror[1] and "--exclude=/_builds/" in mirror[1]
    assert mirror[1][-2:] == ("/mnt/c/repo/", f"/home/me/.ptk/mirrors/{run.name}/")
    create = next(c for c in engine.calls if c[0] == "create")
    assert create[2]["mounts"] == [f"/home/me/.ptk/mirrors/{run.name}:/workspace"]
    assert create[2]["env"] == {
        "HOME": "/workspace/.ptk/home",
        "http_proxy": "http://host.docker.internal:3128",
    }
    values = next(c for c in engine.calls if c[0] == "exec")[2]["values"]
    assert values == {
        "PTK_CX": "0",
        "PTK_USER": "ade7pl",
        "NO_PROXY": "localhost",
        "TOKEN": "s3cret",
    }

    run.copy_back(
        [
            str(project.root / "_bin/default/build"),
            str(project.root / "_logs/default/build"),
            str(project.root / "_builds/inputs"),
        ]
    )
    back = [c for c in engine.calls if c[0] == "rsync"][-1][1]
    mirror_root = f"/home/me/.ptk/mirrors/{run.name}/./"
    assert [a for a in back if a.startswith(mirror_root)] == [
        mirror_root + "_bin/default/build",
        mirror_root + "_logs/default/build",
        mirror_root + "_builds/inputs",
    ]
    assert "not synced back to Windows" in capsys.readouterr().out
    run.copy_back([str(project.root / "_bin/default/build")])
    assert "not synced back" not in capsys.readouterr().out
    clear = next(c for c in engine.calls if c[0] == "call")[1]
    assert clear[:2] == ("rm", "-rf") and clear[2].endswith("/.ptk/locks")


def test_leftovers_of_an_interrupted_run_are_stopped_before_syncing(write, load):
    engine = FakeEngine()
    engine.state = (True, "any")
    engine.processes_running = 5
    run, _ = _run(write, load, engine)
    run.prepare()
    names = engine.names()
    assert names.index("restart") < names.index("rsync")


def test_mounted_vmr_member_works_in_its_folder_of_the_workspace(write, load):
    engine = FakeEngine(windows=False)
    run, project = _run(write, load, engine)
    run.state.app.workspace = SimpleNamespace(root=lambda path: path.parent)
    run.run(["ptk", "run", "build"], secrets={}, cx=False)
    create = next(c for c in engine.calls if c[0] == "create")
    assert create[2]["workdir"] == f"/workspace/{project.root.name}"
    assert next(c for c in engine.calls if c[0] == "exec")[2]["workdir"] == (
        f"/workspace/{project.root.name}"
    )


def test_cancelled_run_reports_130_and_releases_the_lock(write, load):
    engine = FakeEngine()
    run, project = _run(write, load, engine)

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    engine.exec = interrupted
    with run.reserved():
        assert run.run(["ptk", "run", "build"], secrets={}, cx=False) == 130
    assert not (project.root / ".ptk" / "docker.lock").exists()


def test_repository_lock_waits_and_removes_a_stale_lock(write, load):
    run, project = _run(write, load, FakeEngine())
    lock = project.root / ".ptk" / "docker.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("999999999", encoding="utf-8")  # owner process is gone
    with run.reserved():
        assert lock.read_text(encoding="utf-8") != "999999999"
    assert not lock.exists()


def test_changed_settings_recreate_and_linux_mounts_directly(write, load):
    engine = FakeEngine(windows=False)
    engine.state = (True, "outdated")
    run, _ = _run(write, load, engine)
    run.prepare()
    assert "rsync" not in engine.names()
    assert engine.names().index("remove") < engine.names().index("create")
    create = next(c for c in engine.calls if c[0] == "create")
    assert create[2]["mounts"] == ["/mnt/c/repo:/workspace"]
    run.copy_back([])
    assert engine.names().count("rsync") == 0


def test_dry_run_shows_the_container_command(write):
    root = write(project_files(PROJECT))
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["--docker", "build", "--dry-run", "--jobs", "3"], cwd=root
    )
    assert "docker: would run in ptk-demo-" in result.output
    assert "ptk run build -p jobs=3" in result.output.replace("\n", "")


def test_gui_and_host_only_jobs_stay_on_the_host(write):
    root = write(project_files(PROJECT))
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["--docker", "host-only", "--dry-run"], cwd=root
    )
    assert "runs on the host (docker: false)" in result.output
    assert "would run in" not in result.output
