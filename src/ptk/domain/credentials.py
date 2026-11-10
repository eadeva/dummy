"""Credential conventions (pure).

A secret is addressed as ``credential.field`` (``artifactory.token``); the
field defaults to the credential's first field. Where each provider looks:

* env:    ``credentials.<name>.env.<field>``, else ``<PROJECT>_<USER>_<NAME>_<FIELD>``
          (``<PROJECT>_<USER>_<FIELD>`` when field and name are equal; in CX any user
          ID matches), else ``PTK_CRED_<NAME>_<FIELD>``
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
    """Environment variable read by the env provider when nothing else applies."""
    return f"PTK_CRED_{_ident(credential)}_{_ident(field)}"


def convention_suffix(credential: str, field: str) -> str:
    """``ARTIFACTORY_RB_TOKEN`` for ``artifactory_rb.token``, ``PASSWORD`` for ``password.password``."""
    if credential == field:
        return _ident(field)
    return f"{_ident(credential)}_{_ident(field)}"


def convention_variable(project: str, user: str, credential: str, field: str) -> str:
    """``<PROJECT>_<USER>_<CREDENTIAL>_<FIELD>``, e.g. ``TOYOTA_CGW_TET6YH_FOSSID_TOKEN``."""
    return f"{_ident(project)}_{_ident(user)}_{convention_suffix(credential, field)}"


def convention_pattern(project: str, credential: str, field: str) -> str:
    """Matches the convention variable of any user; group 1 is the user ID."""
    return (
        rf"^{re.escape(_ident(project))}_([0-9A-Z]+)_"
        rf"{re.escape(convention_suffix(credential, field))}$"
    )


@dataclass(frozen=True)
class SecretKey:
    credential: str
    field: str
    env_var: str
    namespace: str | None = None
    env_pattern: str | None = None  # convention variable of any user (CX)
    env_fallbacks: tuple[str, ...] = ()

    @property
    def storage_ref(self) -> str:
        return f"{self.namespace}/{self.ref}" if self.namespace else self.ref

    @property
    def ref(self) -> str:
        return f"{self.credential}.{self.field}"

    @property
    def env_vars(self) -> tuple[str, ...]:
        return (self.env_var, *self.env_fallbacks)


def key_for(
    name: str,
    field: str,
    spec: CredentialSpec,
    *,
    project: str | None = None,
    user: str | None = None,
) -> SecretKey:
    scoped_name = f"{spec.namespace}/{name}" if spec.namespace else name
    fallback = default_variable(scoped_name, field)
    if field in spec.env:
        env_var, pattern, fallbacks = spec.env[field], None, ()
    elif project:
        env_var = convention_variable(project, user or "USER", name, field)
        pattern, fallbacks = convention_pattern(project, name, field), (fallback,)
    else:
        env_var, pattern, fallbacks = fallback, None, ()
    return SecretKey(
        namespace=spec.namespace,
        credential=name,
        field=field,
        env_var=env_var,
        env_pattern=pattern,
        env_fallbacks=fallbacks,
    )


def parse_ref(
    ref: str,
    credentials: dict[str, CredentialSpec],
    *,
    project: str | None = None,
    user: str | None = None,
) -> SecretKey:
    name, _, field = ref.partition(".")
    spec = credentials.get(name)
    if spec is None:
        raise PtkError(f"unknown credential '{name}'{did_you_mean(name, credentials)}")
    field = field or spec.fields[0]
    if field not in spec.fields:
        raise PtkError(
            f"credential '{name}' has no field '{field}'{did_you_mean(field, spec.fields)}"
        )
    return key_for(name, field, spec, project=project, user=user)
