"""Credential chain (use case ``CredentialService``).

For each credential the configured providers are tried in order
(default ``env -> keyring -> gopass -> vault -> prompt``); the first value
wins and is cached for the rest of the ptk run. Values are never printed,
logged or passed as command arguments.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ...domain.config.model import CredentialSpec
from ...domain.credentials import SecretKey, parse_ref
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
    ):
        self._credentials = dict(credentials)
        self._providers = dict(providers)
        self._host = host
        self._runner = runner
        self._root = root
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

    def keys(self, name: str, field_name: str | None = None) -> list[SecretKey]:
        spec = self.spec(name)
        fields = [field_name] if field_name else spec.fields
        return [parse_ref(f"{name}.{f}", self._credentials) for f in fields]

    def __call__(self, ref: str) -> str:
        """SecretResolver port: ``credential.field`` -> value."""
        return self.resolve(ref)

    def resolve(self, ref: str) -> str:
        key = parse_ref(ref, self._credentials)
        if key.ref in self._cache:
            return self._cache[key.ref]
        notes: list[str] = []
        for name in self.spec(key.credential).providers:
            value = self._try(name, key, notes)
            if value:
                self._cache[key.ref] = value
                return value
        raise PtkError(
            f"credential '{key.ref}' is not available:\n  - "
            + "\n  - ".join(notes)
            + f"\n  store it with: ptk setup creds set {key.credential}"
            + (f" {key.field}" if len(self.spec(key.credential).fields) > 1 else "")
        )

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
            for key in self.keys(cred):
                notes: list[str] = []
                supplier = None
                for provider in self.spec(cred).providers:
                    usable = self._providers.get(provider)
                    if (
                        provider == "prompt"
                        or usable is None
                        or not usable.available()[0]
                    ):
                        continue  # 'ptk setup creds setup' explains unavailable providers
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
        for provider_name in self.spec(name).providers:
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
            for provider_name in [store] if store else self.spec(name).providers:
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
            env[key.env_var] = value
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
