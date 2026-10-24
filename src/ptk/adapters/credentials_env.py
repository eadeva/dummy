"""Environment-variable secret provider (first link of the credential chain).

``credential.field`` is read from the variable mapped in ``credentials.<name>.env``
or, if not mapped, from ``PTK_CRED_<NAME>_<FIELD>``. gopass, the vault and the
prompt are added in M6 behind the same SecretResolver port.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..domain.config.model import CredentialSpec
from ..domain.credentials import default_variable
from ..domain.errors import PtkError
from ..domain.suggest import did_you_mean


class EnvSecretResolver:
    def __init__(
        self, credentials: Mapping[str, CredentialSpec], environ: Mapping[str, str]
    ):
        self._credentials = credentials
        self._environ = environ

    def __call__(self, ref: str) -> str:
        name, _, field = ref.partition(".")
        spec = self._credentials.get(name)
        if spec is None:
            raise PtkError(
                f"unknown credential '{name}'{did_you_mean(name, self._credentials)}"
            )
        field = field or spec.fields[0]
        if field not in spec.fields:
            raise PtkError(
                f"credential '{name}' has no field '{field}'{did_you_mean(field, spec.fields)}"
            )
        variable = spec.env.get(field) or default_variable(name, field)
        value = self._environ.get(variable)
        if not value:
            raise PtkError(
                f"credential '{name}.{field}' is not available: set {variable} "
                "(gopass, vault and prompt providers follow in a later version)"
            )
        return value
