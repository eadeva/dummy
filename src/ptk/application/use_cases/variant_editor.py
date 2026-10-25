"""GUI-independent editing session, validating the complete effective project."""

from dataclasses import dataclass

import yaml
from pydantic import ValidationError

from ...domain.config.model import PtkConfig
from ...domain.config.rules import validate
from ...domain.errors import PtkError
from ...domain.variants.rules import resolve


@dataclass
class VariantEditorSession:
    config: PtkConfig

    def initial_text(self) -> str:
        if self.config.variants is None:
            raise PtkError("this project has no 'variants' section")
        return yaml.safe_dump(
            self.config.variants.model_dump(mode="json"), sort_keys=False
        )

    def validate(self, text: str) -> PtkConfig:
        try:
            variants = yaml.safe_load(text)
            if not isinstance(variants, dict):
                raise PtkError("the editor expects a product-line YAML mapping")
            data = self.config.model_dump(mode="json", by_alias=True)
            data["variants"] = variants
            config = PtkConfig.model_validate(data)
        except (yaml.YAMLError, ValidationError) as exc:
            raise PtkError(f"invalid variant edit: {exc}") from None
        problems = [f"{'.'.join(map(str, p))}: {m}" for p, m in validate(config)]
        if problems:
            raise PtkError("\n".join(problems))
        assert config.variants is not None
        for name in config.variants.buildable():
            problems.extend(
                f"{name}: {issue}" for issue in resolve(config.variants, name).errors
            )
        if problems:
            raise PtkError("\n".join(problems))
        return config

    def render(self, text: str) -> str:
        config = self.validate(text)
        return yaml.safe_dump(
            config.model_dump(mode="json", by_alias=True, exclude_defaults=True),
            sort_keys=False,
            allow_unicode=True,
        )
