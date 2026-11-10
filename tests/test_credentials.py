"""Credential chain: env, keyring, gopass, vault, prompt; ptk self-service creds commands."""

from __future__ import annotations

import json
import os
import stat
import sys
import types
from pathlib import Path

import pytest

from ptk.adapters.credentials.env import EnvProvider
from ptk.adapters.credentials.gopass import GopassProvider
from ptk.adapters.credentials.keyring_provider import KeyringProvider
from ptk.adapters.credentials.prompt import PromptProvider
from ptk.adapters.credentials.vault import Vault, VaultProvider
from ptk.application.use_cases.credentials import CredentialService
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import CredentialSpec
from ptk.domain.credentials import key_for
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


class WindowsHost(Host):
    def os_name(self):
        return "windows"


class FakeKeyring:
    name = "keyring"
    can_store = True

    def __init__(self, values=None):
        self.values = dict(values or {})

    def available(self):
        return True, ""

    def get(self, key):
        return self.values.get(key.ref)

    def store(self, key, value):
        self.values[key.ref] = value

    def remove(self, key):
        return self.values.pop(key.ref, None) is not None


def test_windows_prefers_the_vault_and_remembers_prompts_there(tmp_path):
    keyring = FakeKeyring({"art.token": "from-keyring"})
    providers = {
        "env": EnvProvider({}),
        "keyring": keyring,
        "vault": VaultProvider(vault(tmp_path)),
        "prompt": PromptProvider(FakePrompter(["typed-user"])),
    }
    svc = CredentialService({"art": SPEC}, providers, WindowsHost())
    assert svc.providers("art") == ["env", "vault", "keyring", "gopass", "prompt"]
    assert svc.stores("art") == ["vault", "keyring"]
    assert svc.resolve("art.token") == "from-keyring"  # existing entries still work
    assert svc.resolve("art.user") == "typed-user"
    assert vault(tmp_path).entries() == {"art.user": "typed-user"}
    assert keyring.values == {"art.token": "from-keyring"}
    vault(tmp_path).set("art.token", "from-vault")
    providers["vault"] = VaultProvider(vault(tmp_path))
    fresh = CredentialService({"art": SPEC}, providers, WindowsHost())
    assert fresh.resolve("art.token") == "from-vault"
    explicit = CredentialSpec(providers=["env", "keyring"])
    assert CredentialService({"art": explicit}, providers, WindowsHost()).providers(
        "art"
    ) == ["env", "keyring"]


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


# --------------------------------------------------------------------------- keyring


@pytest.fixture
def fake_keyring(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    module = types.ModuleType("keyring")
    errors = types.ModuleType("keyring.errors")
    errors.KeyringError = Exception

    class PasswordDeleteError(Exception):
        pass

    errors.PasswordDeleteError = PasswordDeleteError

    class Backend:
        priority = 5

    module.get_keyring = lambda: Backend()
    module.get_password = lambda service, user: store.get((service, user))
    module.set_password = lambda service, user, value: store.__setitem__(
        (service, user), value
    )

    def delete(service, user):
        if (service, user) not in store:
            raise PasswordDeleteError(user)
        del store[(service, user)]

    module.delete_password = delete
    module.errors = errors
    monkeypatch.setitem(sys.modules, "keyring", module)
    monkeypatch.setitem(sys.modules, "keyring.errors", errors)
    return store


def test_keyring_provider(tmp_path, fake_keyring):
    provider = KeyringProvider()
    assert provider.available() == (True, "")
    svc = service(
        tmp_path,
        extra={"keyring": provider},
        spec=CredentialSpec(fields=["token"], providers=["env", "keyring", "vault"]),
    )
    assert svc.stores("art")[0] == "keyring"
    svc.store("art", None, "kr-secret", None)
    assert fake_keyring == {("ptk", "art.token"): "kr-secret"}
    assert (
        service(
            tmp_path,
            extra={"keyring": KeyringProvider()},
            spec=CredentialSpec(providers=["keyring"]),
        ).resolve("art.token")
        == "kr-secret"
    )


def test_keyring_remove_reports_backend_failures(fake_keyring, monkeypatch):
    from ptk.domain.credentials import SecretKey

    provider = KeyringProvider()
    key = SecretKey("art", "token", "ART_TOKEN", "ptk/art/token")
    provider.store(key, "kr-secret")
    assert provider.remove(key) is True
    assert provider.remove(key) is False

    def locked(service, user):
        raise RuntimeError("keyring is locked")

    monkeypatch.setattr(sys.modules["keyring"], "delete_password", locked)
    with pytest.raises(PtkError, match="keyring is locked"):
        provider.remove(key)


def test_keyring_missing_is_skipped(monkeypatch):
    monkeypatch.setitem(sys.modules, "keyring", None)  # import fails
    ok, reason = KeyringProvider().available()
    assert not ok and "xcce_ptk[keyring]" in reason


# --------------------------------------------------------------------------- gopass

FAKE_GOPASS = """#!/bin/sh
# stand-in for gopass: entries are files below $GOPASS_DIR
cmd=$1; shift
case "$cmd" in
  show) [ "$1" = "--password" ] && shift; f="$GOPASS_DIR/$1"
        [ -f "$f" ] || { echo "entry not found" >&2; exit 11; }; head -n1 "$f" ;;
  insert) [ "$1" = "--force" ] && shift; mkdir -p "$(dirname "$GOPASS_DIR/$1")"
          cat > "$GOPASS_DIR/$1" ;;
  rm) [ "$1" = "--force" ] && shift; rm "$GOPASS_DIR/$1" ;;
esac
"""


@pytest.mark.skipif(not POSIX, reason="shell stand-in")
def test_gopass_provider_uses_stdin_and_paths(tmp_path, monkeypatch):
    exe = tmp_path / "gopass"
    exe.write_text(FAKE_GOPASS)
    exe.chmod(0o755)
    monkeypatch.setenv("GOPASS_DIR", str(tmp_path / "store"))
    provider = GopassProvider(str(exe))
    spec = CredentialSpec(fields=["token"], gopass={"path": "team/artifactory"})
    key = key_for("art", "token", spec)
    assert key.gopass_path == "team/artifactory/token"
    assert provider.get(key) is None
    provider.store(key, "gp-secret")
    assert (tmp_path / "store/team/artifactory/token").read_text() == "gp-secret\n"
    assert provider.get(key) == "gp-secret"
    assert provider.remove(key) and provider.get(key) is None
    assert GopassProvider(executable=None).available()[0] in (True, False)


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
    result = cli_env("self-service", "creds", "setup", "--vault")
    assert result.exit_code == 0 and "vault created" in result.output
    assert Path(cli_env.env["PTK_VAULT_FILE"]).is_file()
    again = cli_env("self-service", "creds", "setup", "--vault")
    assert again.exit_code == 2 and "already exists" in again.output


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
