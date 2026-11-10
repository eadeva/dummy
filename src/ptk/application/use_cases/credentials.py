"""Credential chain (use case ``CredentialService``).

For each credential the configured providers are tried in order
(default ``env -> keyring -> gopass -> vault -> prompt``); the first value
wins and is cached for the rest of the ptk run. Values are never printed,
logged or passed as command arguments.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from ...domain.config.model import CredentialSpec
from ...domain.credentials import (
    SecretKey,
    default_variable,
    parse_ref,
    provider_chain,
)
from ...domain.errors import PtkError
from ...domain.execution.model import CommandSpec
from ...domain.suggest import did_you_mean
from ..ports import HostEnvironment, ProcessRunner, SecretProvider

MASK = "********"


@dataclass
class SecretStatus:
    key: SecretKey
    provider: str | None  # who supplies it now (None: missing)
    notes: list[str] = field(default_factory=list)


class CredentialService:
    def __init__(
        self,
        credentials: Mapping[str, CredentialSpec],
        providers: Mapping[str, SecretProvider],
        host: HostEnvironment,
        runner: ProcessRunner | None = None,
        root: Path | None = None,
        project: str | None = None,
    ):
        self._credentials = dict(credentials)
        self._providers = dict(providers)
        self._host = host
        self._runner = runner
        self._root = root
        self._project = project
        self._cache: dict[str, str] = {}

    # -- lookups -----------------------------------------------------------------------

    def spec(self, name: str) -> CredentialSpec:
        if name not in self._credentials:
            known = self._credentials
            hint = did_you_mean(name, known) or (
                f" (credentials: {', '.join(known)})"
                if known
                else " - none are configured"
            )
            raise PtkError(f"unknown credential '{name}'{hint}")
        return self._credentials[name]

    def providers(self, name: str) -> list[str]:
        return provider_chain(self.spec(name), self._host.os_name())

    def keys(self, name: str, field_name: str | None = None) -> list[SecretKey]:
        spec = self.spec(name)
        fields = [field_name] if field_name else spec.fields
        return [self._key(f"{name}.{f}") for f in fields]

    def _key(self, ref: str) -> SecretKey:
        cx = self._host.is_cx()
        key = parse_ref(
            ref,
            self._credentials,
            project=self._project,
            user=None if cx else self._host.user_id(),
        )
        # Locally only the running user's variable counts; in CX the technical user is any ID.
        return key if cx else replace(key, env_pattern=None)

    def __call__(self, ref: str) -> str:
        """SecretResolver port: ``credential.field`` -> value."""
        return self.resolve(ref)

    def resolve(self, ref: str) -> str:
        key = self._key(ref)
        if key.ref in self._cache:
            return self._cache[key.ref]
        spec = self.spec(key.credential)
        notes: list[str] = []
        if key.field == spec.user_field:
            value = self._account(key, notes)
            if value:
                self._cache[key.ref] = value
                return value
            raise PtkError(
                f"credential '{key.ref}' is not available:\n  - " + "\n  - ".join(notes)
            )
        for name in self.providers(key.credential):
            value = self._try(name, key, notes)
            if value:
                if name == "prompt" and spec.remember:
                    self._remember(key, value, notes)
                self._cache[key.ref] = value
                return value
        raise PtkError(
            f"credential '{key.ref}' is not available:\n  - "
            + "\n  - ".join(notes)
            + f"\n  store it with: ptk self-service creds set {key.credential}"
            + (f" {key.field}" if len(spec.fields) > 1 else "")
        )

    def _account(self, key: SecretKey, notes: list[str]) -> str | None:
        """The account of ``user_field``: in CX from env (or the user ID in the
        convention variable of another field), else the user running PTK."""
        if self._host.is_cx():
            value = self._try("env", key, notes)
            env = self._providers.get("env")
            for other in self.keys(key.credential):
                if value or other.field == key.field or not hasattr(env, "match"):
                    continue
                found = env.match(other)
                value = found[1] if found else None
            return value
        user = (self._host.user_id() or "").lower()
        if not user:
            notes.append("user: the user running PTK is unknown")
        return user or None

    def _remember(self, key: SecretKey, value: str, notes: list[str]) -> None:
        stores = self.stores(key.credential)
        if not stores:
            return
        try:
            self._providers[stores[0]].store(key, value)
        except PtkError as exc:
            notes.append(f"{stores[0]}: not stored ({exc})")

    def _try(self, name: str, key: SecretKey, notes: list[str]) -> str | None:
        provider = self._providers.get(name)
        if provider is None:
            notes.append(f"{name}: not supported here")
            return None
        ok, reason = provider.available()
        if not ok:
            notes.append(f"{name}: {reason}")
            return None
        try:
            value = provider.get(key)
        except PtkError as exc:
            notes.append(f"{name}: {exc}")
            return None
        if not value:
            where = {
                "env": f"{key.env_var} is not set",
                "gopass": f"no entry {key.gopass_path}",
                "vault": f"no entry {key.ref}",
                "keyring": f"no entry ptk/{key.ref}",
            }.get(name, "no value")
            notes.append(f"{name}: {where}")
        return value

    def status(self, name: str | None = None) -> list[SecretStatus]:
        """Who would supply each secret - without asking anyone (no prompt)."""
        names = [name] if name else list(self._credentials)
        result = []
        for cred in names:
            spec = self.spec(cred)
            for key in self.keys(cred):
                notes: list[str] = []
                supplier = None
                if key.field == spec.user_field and not self._host.is_cx():
                    result.append(SecretStatus(key, "user", ["the user running PTK"]))
                    continue
                for provider in self.providers(cred):
                    usable = self._providers.get(provider)
                    if (
                        provider == "prompt"
                        or usable is None
                        or not usable.available()[0]
                    ):
                        continue  # 'ptk self-service creds setup' explains unavailable providers
                    if provider == "env":
                        if self._try(provider, key, notes):
                            supplier = provider
                            break
                    else:
                        # Never retrieve/unlock secrets just to list metadata.
                        supplier = provider
                        notes.append(
                            "provider available; stored value not read or verified"
                        )
                        break
                result.append(SecretStatus(key, supplier, notes))
        return result

    # -- changes -----------------------------------------------------------------------

    def stores(self, name: str) -> list[str]:
        """Providers that can store this credential here, in chain order."""
        result = []
        for provider_name in self.providers(name):
            provider = self._providers.get(provider_name)
            if provider is None or not provider.can_store:
                continue
            ok, _ = provider.available()
            if ok or provider_name == "vault":  # the vault is created on first use
                result.append(provider_name)
        return result

    def store(
        self, name: str, field_name: str | None, value: str, store: str | None
    ) -> str:
        if not value:
            raise PtkError("empty value - nothing stored")
        [key] = self.keys(name, field_name or self.spec(name).fields[0])
        candidates = self.stores(name)
        target = store or (candidates[0] if candidates else None)
        if target is None:
            raise PtkError(f"no provider can store '{key.ref}' here")
        if target not in self._providers or not self._providers[target].can_store:
            raise PtkError(
                f"'{target}' cannot store secrets (choose: {', '.join(candidates)})"
            )
        self._providers[target].store(key, value)
        self._cache[key.ref] = value
        return target

    def remove(self, name: str, field_name: str | None, store: str | None) -> list[str]:
        removed = []
        for key in self.keys(name, field_name):
            for provider_name in [store] if store else self.providers(name):
                provider = self._providers.get(provider_name or "")
                if provider is not None and provider.can_store and provider.remove(key):
                    removed.append(f"{key.ref} from {provider_name}")
            self._cache.pop(key.ref, None)
        return removed

    def test(self, name: str) -> tuple[bool, list[str]]:
        """Run the credential's ``test`` command with its secrets as env variables."""
        spec = self.spec(name)
        if not spec.test:
            raise PtkError(f"credential '{name}' has no 'test' command configured")
        if self._runner is None:
            raise PtkError("no process runner available")
        env = dict(self._host.variables)
        secrets = []
        for key in self.keys(name):
            value = self.resolve(key.ref)
            for variable in {
                *key.env_vars,
                default_variable(key.credential, key.field),
            }:
                env[variable] = value
            secrets.append(value)
        lines: list[str] = []

        def masked(line: str) -> None:
            for value in sorted(secrets, key=len, reverse=True):
                if len(value) >= 4:
                    line = line.replace(value, MASK)
            lines.append(line)

        outcome = self._runner.run(
            CommandSpec(
                shell=spec.test, cwd=str(self._root or "."), env=env, timeout=120
            ),
            masked,
        )
        if outcome.error:
            lines.append(outcome.error)
        return outcome.exit_code == 0, lines
