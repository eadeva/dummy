"""Credential chain: env, vault, prompt; ptk self-service creds commands."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from ptk.adapters.credentials.env import EnvProvider
from ptk.adapters.credentials.prompt import PromptProvider
from ptk.adapters.credentials.session import VaultSession
from ptk.adapters.credentials.vault import Vault, VaultProvider
from ptk.application.use_cases.credentials import CredentialService
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import CredentialSpec
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import project_files

POSIX = not sys.platform.startswith("win")
HOST = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}


class Host:
    def __init__(self, variables=None):
        self.variables = variables or {}

    def is_cx(self):
        return False

    def os_name(self):
        return "linux"

    def user_id(self):
        return None


class FakePrompter:
    def __init__(self, answers=(), interactive=True):
        self.answers = list(answers)
        self.asked: list[str] = []
        self._interactive = interactive

    def interactive(self):
        return self._interactive

    def secret(self, question):
        self.asked.append(question)
        return self.answers.pop(0)


def vault(tmp_path: Path, password="correct horse") -> Vault:
    return Vault(tmp_path / "vault.json", lambda confirm: password)


SPEC = CredentialSpec(fields=["user", "token"], env={"token": "ART_TOKEN"})


# --------------------------------------------------------------------------- vault


def test_vault_roundtrip_and_encryption(tmp_path):
    v = vault(tmp_path)
    v.set("artifactory.token", "s3cr3t-value")
    raw = (tmp_path / "vault.json").read_text()
    assert "s3cr3t-value" not in raw and "artifactory" not in raw  # names encrypted too
    doc = json.loads(raw)
    assert doc["cipher"] == "AES-256-GCM" and doc["kdf"]["name"] == "scrypt"
    if POSIX:
        assert stat.S_IMODE((tmp_path / "vault.json").stat().st_mode) == 0o600
    assert vault(tmp_path).entries() == {"artifactory.token": "s3cr3t-value"}
    first_nonce = doc["nonce"]
    v.set("other.token", "x" * 10)
    assert json.loads((tmp_path / "vault.json").read_text())["nonce"] != first_nonce


def test_vault_wrong_password_and_tampering(tmp_path):
    vault(tmp_path).set("a.b", "value-1")
    with pytest.raises(PtkError, match="wrong vault password"):
        vault(tmp_path, password="wrong one!").entries()
    doc = json.loads((tmp_path / "vault.json").read_text())
    data = bytearray(doc["data"].encode())
    data[5] = ord("A") if data[5] != ord("A") else ord("B")
    doc["data"] = data.decode()
    (tmp_path / "vault.json").write_text(json.dumps(doc))
    with pytest.raises(PtkError, match="modified"):
        vault(tmp_path).entries()


def test_vault_password_rules(tmp_path):
    with pytest.raises(PtkError, match="at least 8"):
        Vault(tmp_path / "v.json", lambda confirm: "short").create()


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def session(tmp_path, clock, hours="8"):
    environ = {
        "LOCALAPPDATA": str(tmp_path / "local"),
        "XDG_RUNTIME_DIR": str(tmp_path / "run"),
        "PTK_VAULT_UNLOCK_HOURS": hours,
    }
    return VaultSession(tmp_path / "vault.json", environ, now=clock)


def asking(tmp_path, clock, asked, password="correct horse"):
    def ask(confirm):
        asked.append(confirm)
        return password

    return Vault(tmp_path / "vault.json", ask, session(tmp_path, clock))


def test_session_keeps_the_vault_unlocked_until_it_expires(tmp_path):
    clock, asked = Clock(), []
    asking(tmp_path, clock, asked).set("art.token", "value-1")
    assert asked == [True]
    stored = session(tmp_path, clock).file.read_bytes()
    assert b"correct horse" not in stored and b"value-1" not in stored
    assert asking(tmp_path, clock, asked).entries() == {"art.token": "value-1"}
    assert asked == [True]  # next run: no password
    clock.now += 8 * 3600
    assert asking(tmp_path, clock, asked).entries() == {"art.token": "value-1"}
    assert asked == [True, False]


def test_lock_and_disabled_sessions(tmp_path):
    clock, asked = Clock(), []
    first = asking(tmp_path, clock, asked)
    first.set("a.b", "value-1")
    assert first.lock() is True and first.lock() is False
    asking(tmp_path, clock, asked).entries()
    assert asked == [True, False]
    assert not session(tmp_path, clock, hours="0").enabled
    with pytest.raises(PtkError, match="PTK_VAULT_UNLOCK_HOURS"):
        session(tmp_path, clock, hours="soon")


def test_session_of_a_replaced_vault_is_ignored(tmp_path):
    clock, asked = Clock(), []
    asking(tmp_path, clock, asked).set("a.b", "old")
    (tmp_path / "vault.json").unlink()
    Vault(tmp_path / "vault.json", lambda c: "other password").set("a.b", "new")
    assert asking(tmp_path, clock, asked, "other password").entries() == {"a.b": "new"}
    assert asked == [True, False]


def test_reset_deletes_vault_and_session(tmp_path):
    clock, asked = Clock(), []
    v = asking(tmp_path, clock, asked)
    v.set("a.b", "value-1")
    assert v.delete() is True
    assert not (tmp_path / "vault.json").exists()
    assert not session(tmp_path, clock).file.exists()
    assert v.delete() is False


# --------------------------------------------------------------------------- chain


def service(tmp_path, *, env=None, prompter=None, extra=None, spec=SPEC):
    providers = {
        "env": EnvProvider(env or {}),
        "vault": VaultProvider(vault(tmp_path)),
        "prompt": PromptProvider(prompter or FakePrompter(interactive=False)),
        **(extra or {}),
    }
    return CredentialService({"art": spec}, providers, Host())


def test_first_provider_wins_and_is_cached(tmp_path):
    svc = service(tmp_path, env={"ART_TOKEN": "from-env"})
    vault(tmp_path).set("art.token", "from-vault")
    assert svc.resolve("art.token") == "from-env"
    assert svc.resolve("art.token") == "from-env"  # cached
    svc2 = service(tmp_path)
    assert svc2.resolve("art.token") == "from-vault"


def test_missing_lists_what_was_tried(tmp_path):
    svc = service(tmp_path)
    with pytest.raises(PtkError) as info:
        svc.resolve("art.user")
    text = str(info.value)
    assert "env: PTK_CRED_ART_USER is not set" in text
    assert "vault: no vault yet" in text and "prompt: not interactive" in text
    assert "ptk self-service creds set art user" in text


def test_prompt_is_last_and_only_interactive(tmp_path):
    prompter = FakePrompter(["typed-value"])
    svc = service(tmp_path, prompter=prompter)
    assert svc.resolve("art.user") == "typed-value"
    assert svc.resolve("art.user") == "typed-value"  # asked once per run
    assert len(prompter.asked) == 1


def test_status_never_prompts(tmp_path):
    prompter = FakePrompter(["never"])
    svc = service(tmp_path, env={"ART_TOKEN": "x" * 8}, prompter=prompter)
    rows = {r.key.ref: r for r in svc.status()}
    assert rows["art.token"].provider == "env" and rows["art.user"].provider is None
    assert prompter.asked == []


def test_store_and_remove(tmp_path):
    svc = service(tmp_path)
    assert svc.stores("art") == ["vault"]
    assert svc.store("art", "token", "tok-123456", None) == "vault"
    assert vault(tmp_path).entries() == {"art.token": "tok-123456"}
    with pytest.raises(PtkError, match="cannot store"):
        svc.store("art", "token", "v", "env")
    assert svc.remove("art", None, None) == ["art.token from vault"]


def test_unknown_credential_and_field(tmp_path):
    svc = service(tmp_path)
    with pytest.raises(PtkError, match="did you mean 'art'"):
        svc.resolve("arts.token")
    with pytest.raises(PtkError, match="did you mean 'token'"):
        svc.resolve("art.tokn")


def test_only_env_vault_and_prompt_are_providers(tmp_path):
    providers = {
        "env": EnvProvider({}),
        "vault": VaultProvider(vault(tmp_path)),
        "prompt": PromptProvider(FakePrompter(["typed-user"])),
    }
    svc = CredentialService({"art": SPEC}, providers, Host())
    assert svc.providers("art") == ["env", "vault", "prompt"]
    assert svc.stores("art") == ["vault"]
    assert svc.resolve("art.user") == "typed-user"
    assert vault(tmp_path).entries() == {"art.user": "typed-user"}
    for removed in ("keyring", "gopass"):
        with pytest.raises(ValueError, match="providers"):
            CredentialSpec(providers=["env", removed])
    with pytest.raises(ValueError, match="gopass"):
        CredentialSpec(gopass={"path": "team/x"})


class UserHost(Host):
    def __init__(self, cx=False):
        super().__init__()
        self._cx = cx

    def is_cx(self):
        return self._cx

    def user_id(self):
        return "ABC1XY"


USER_SPEC = CredentialSpec(
    fields=["user", "token"],
    user_field="user",
    env={"user": "TECH_USER", "token": "ART_TOKEN"},
)


def test_user_field_is_the_running_user_outside_cx(tmp_path):
    providers = {"env": EnvProvider({"TECH_USER": "techuser"})}
    svc = CredentialService({"art": USER_SPEC}, providers, UserHost())
    assert svc.resolve("art.user") == "abc1xy"
    assert {r.key.ref: r.provider for r in svc.status()}["art.user"] == "user"
    cx = CredentialService({"art": USER_SPEC}, providers, UserHost(cx=True))
    assert cx.resolve("art.user") == "techuser"


def test_prompted_value_is_remembered_unless_disabled(tmp_path):
    vault(tmp_path).create()
    svc = service(tmp_path, prompter=FakePrompter(["typed-token"]))
    assert svc.resolve("art.token") == "typed-token"
    assert vault(tmp_path).entries() == {"art.token": "typed-token"}

    other = tmp_path / "other"
    other.mkdir()
    vault(other).create()
    spec = CredentialSpec(fields=["password"], remember=False)
    providers = {
        "vault": VaultProvider(vault(other)),
        "prompt": PromptProvider(FakePrompter(["pw-123456"])),
    }
    svc = CredentialService({"art": spec}, providers, Host())
    assert svc.resolve("art.password") == "pw-123456"
    assert vault(other).entries() == {}


def test_user_field_must_be_a_field():
    with pytest.raises(ValueError, match="user_field"):
        CredentialSpec(fields=["token"], user_field="user")


CONVENTION = {
    "artifactory_rb": CredentialSpec(fields=["user", "token"], user_field="user"),
    "password": CredentialSpec(fields=["password", "user"], user_field="user"),
}


def convention_service(env, *, cx):
    providers = {"env": EnvProvider(env)}
    return CredentialService(
        CONVENTION, providers, UserHost(cx=cx), project="toyota_cgw"
    )


def test_cx_reads_project_user_credential_variables():
    env = {
        "TOYOTA_CGW_TET6YH_ARTIFACTORY_RB_TOKEN": "rb-token",
        "TOYOTA_CGW_TET6YH_PASSWORD": "pw-value",
    }
    svc = convention_service(env, cx=True)
    assert svc.resolve("artifactory_rb.token") == "rb-token"
    assert svc.resolve("artifactory_rb.user") == "tet6yh"
    assert svc.resolve("password.password") == "pw-value"
    assert svc.resolve("password.user") == "tet6yh"


def test_local_runs_only_read_the_running_users_variables():
    env = {
        "TOYOTA_CGW_TET6YH_ARTIFACTORY_RB_TOKEN": "techuser-token",
        "TOYOTA_CGW_ABC1XY_ARTIFACTORY_RB_TOKEN": "own-token",
    }
    svc = convention_service(env, cx=False)
    assert svc.resolve("artifactory_rb.token") == "own-token"
    assert svc.resolve("artifactory_rb.user") == "abc1xy"
    with pytest.raises(PtkError, match="TOYOTA_CGW_ABC1XY_PASSWORD is not set"):
        svc.resolve("password.password")


def test_cx_rejects_several_users_for_one_credential():
    env = {
        "TOYOTA_CGW_TET6YH_ARTIFACTORY_RB_TOKEN": "a",
        "TOYOTA_CGW_OTHER1_ARTIFACTORY_RB_TOKEN": "b",
    }
    with pytest.raises(PtkError, match="several users"):
        convention_service(env, cx=True).resolve("artifactory_rb.token")


# --------------------------------------------------------------------------- CLI + run

PROJECT = """\
project:
  name: c
  default_job: go
credentials:
  art:
    fields:
    - token
    providers:
    - env
    - vault
    test: test "$PTK_CRED_ART_TOKEN" = "vault-secret-1" && echo token is $PTK_CRED_ART_TOKEN
jobs:
  go:
    steps:
      use:
        run: echo got $T
        secrets:
          T: art.token
"""


@pytest.fixture
def cli_env(write, tmp_path):
    root = write(project_files(PROJECT))
    env = {
        **HOST,
        "PTK_VAULT_FILE": str(tmp_path / "v" / "vault.json"),
        "PTK_VAULT_PASSWORD": "master-password-1",
    }

    def invoke(*args, input=None):
        base = []
        return CliRunner(env={"PTK_CX": "0", **env}).invoke(
            cli, [*base, *args], input=input, catch_exceptions=False, cwd=root
        )

    invoke.root = root
    invoke.env = env
    return invoke


@pytest.mark.skipif(not POSIX, reason="POSIX shell")
def test_creds_cli_end_to_end(cli_env):
    missing = cli_env("self-service", "creds", "list")
    assert "missing" in missing.output
    stored = cli_env("self-service", "creds", "set", "art", input="vault-secret-1\n")
    assert stored.exit_code == 0 and "stored art.token in vault" in stored.output
    listing = cli_env("self-service", "creds", "list")
    assert "vault" in listing.output and "vault-secret-1" not in listing.output
    tested = cli_env("self-service", "creds", "test", "art")
    assert tested.exit_code == 0 and "token is ********" in tested.output
    ran = cli_env("go")
    assert ran.exit_code == 0 and "got ********" in ran.output
    assert "vault-secret-1" not in ran.output
    log = (cli_env.root / "_logs/default/go/steps/use.log").read_text()
    assert "vault-secret-1" not in log
    setup = cli_env("self-service", "creds", "setup")
    assert "vault" in setup.output and "ready" in setup.output
    removed = cli_env("self-service", "creds", "remove", "art")
    assert "art.token from vault" in removed.output


def test_creds_setup_creates_vault(cli_env):
    result = cli_env("self-service", "creds", "setup")
    assert result.exit_code == 0 and "vault created" in result.output
    assert Path(cli_env.env["PTK_VAULT_FILE"]).is_file()
    again = cli_env("self-service", "creds", "setup")
    assert again.exit_code == 0 and "vault created" not in again.output
    assert "ready" in again.output


def test_creds_reset_and_lock(cli_env):
    cli_env("self-service", "creds", "setup")
    vault_file = Path(cli_env.env["PTK_VAULT_FILE"])
    refused = cli_env("self-service", "creds", "reset")
    assert refused.exit_code != 0 and "--yes" in refused.output
    assert vault_file.is_file()
    reset = cli_env("self-service", "creds", "reset", "--yes")
    assert reset.exit_code == 0 and "vault deleted" in reset.output
    assert not vault_file.exists()
    assert "no vault" in cli_env("self-service", "creds", "reset", "--yes").output
    locked = cli_env("self-service", "creds", "lock")
    assert locked.exit_code == 0 and "not unlocked" in locked.output


def test_locked_vault_without_terminal(cli_env, tmp_path):
    vault_file = Path(cli_env.env["PTK_VAULT_FILE"])
    Vault(vault_file, lambda c: "master-password-1").set("art.token", "zzzzzzzz")
    env = {k: v for k, v in cli_env.env.items() if k != "PTK_VAULT_PASSWORD"}
    app = create_app(environ=env, prompter=FakePrompter(interactive=False))
    project = app.load_project.execute(cli_env.root)
    with pytest.raises(PtkError, match="vault: the vault is locked"):
        app.prepare_run(project).execute(project, RunRequest())


def test_dry_run_needs_no_secrets(cli_env):
    result = cli_env("run", "--dry-run")
    assert result.exit_code == 0 and "T=********" in result.output
