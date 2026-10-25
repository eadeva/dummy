"""Credential conventions (pure).

A secret is addressed as ``credential.field`` (``artifactory.token``); the
field defaults to the credential's first field. Where each provider looks:

* env:    ``credentials.<name>.env.<field>`` or ``PTK_CRED_<NAME>_<FIELD>``
* gopass: ``credentials.<name>.gopass.path`` + ``/<field>`` (default ``ptk/<name>/<field>``)
* vault:  the key ``<name>.<field>`` (one vault per user, shared by all projects)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config.model import CredentialSpec
from .errors import PtkError
from .suggest import did_you_mean


def _ident(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", text).upper()


def default_variable(credential: str, field: str) -> str:
    """Environment variable read by the env provider when ``env:`` maps nothing."""
    return f"PTK_CRED_{_ident(credential)}_{_ident(field)}"


@dataclass(frozen=True)
class SecretKey:
    credential: str
    field: str
    env_var: str
    gopass_path: str
    namespace: str | None = None

    @property
    def storage_ref(self) -> str:
        return f"{self.namespace}/{self.ref}" if self.namespace else self.ref

    @property
    def ref(self) -> str:
        return f"{self.credential}.{self.field}"


def key_for(name: str, field: str, spec: CredentialSpec) -> SecretKey:
    scoped_name = f"{spec.namespace}/{name}" if spec.namespace else name
    base = spec.gopass.path.rstrip("/") if spec.gopass else f"ptk/{scoped_name}"
    return SecretKey(
        namespace=spec.namespace,
        credential=name,
        field=field,
        env_var=spec.env.get(field) or default_variable(scoped_name, field),
        gopass_path=f"{base}/{field}",
    )


def parse_ref(ref: str, credentials: dict[str, CredentialSpec]) -> SecretKey:
    name, _, field = ref.partition(".")
    spec = credentials.get(name)
    if spec is None:
        raise PtkError(f"unknown credential '{name}'{did_you_mean(name, credentials)}")
    field = field or spec.fields[0]
    if field not in spec.fields:
        raise PtkError(
            f"credential '{name}' has no field '{field}'{did_you_mean(field, spec.fields)}"
        )
    return key_for(name, field, spec)
