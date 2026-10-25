"""Validated patches for persistent variant selection and creation."""

import yaml

from ...domain.errors import PtkError
from ...domain.variants.model import VariantSpec
from .variant_editor import VariantEditorSession
from .variants import VariantService


def variant_patch(
    project,
    name: str,
    features: dict[str, str],
    *,
    create=False,
    extends: str | None = None,
    components: tuple[str, ...] = (),
) -> dict:
    service = VariantService(project)
    line = service.line.model_copy(deep=True)
    if create:
        if name in line.variants or name in line.alias_index():
            raise PtkError(f"variant '{name}' already exists")
        line.variants[name] = VariantSpec(
            extends=[service.name_of(extends)] if extends else [],
            components=list(components) if components else None,
        )
    else:
        name = service.name_of(name)
        if line.variants[name].abstract:
            raise PtkError("cannot select an abstract variant")
        line.default = name
    values = {}
    for feature, text in features.items():
        if feature not in line.feature_index:
            raise PtkError(f"unknown feature '{feature}'")
        try:
            values[feature] = line.feature(feature).parse_text(text)
        except ValueError as exc:
            raise PtkError(f"{feature}: {exc}") from None
    line.variants[name].features.update(values)
    VariantEditorSession(project.config).validate(
        yaml.safe_dump(line.model_dump(mode="json"))
    )
    body = (
        line.variants[name].model_dump(mode="json", exclude_defaults=True)
        if create
        else {"features": values}
    )
    patch = {"variants": {"variants": {name: body}}}
    if not create:
        patch["variants"]["default"] = name
    return patch
