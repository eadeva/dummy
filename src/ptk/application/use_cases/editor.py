"""Read-only editor inventory. Never resolve versions, tools or credentials."""

from dataclasses import asdict

from .role import command_allowed, visible
from .variants import VariantService


def describe_project(project, role):
    """Expose only permitted operations and authored, non-secret parameter metadata."""
    config = project.config
    capabilities = {
        name: command_allowed(path, role, config.command_audience)
        for name, path in {
            "validate": "setup.config.validate",
            "variants": "variant",
            "reports": "report",
            "setup_vscode": "setup.vscode",
        }.items()
    }
    variants = VariantService(project)
    items = (
        variants.list() if variants.has_variants and capabilities["variants"] else []
    )
    return {
        "alias": config.repository.alias,
        "name": config.project.name,
        "root": str(project.root),
        "entry_file": str(project.main_file),
        "config_files": [str(path) for path in project.files],
        "role": role,
        "capabilities": capabilities,
        "default_variant": next((item.name for item in items if item.default), None),
        "variants": [asdict(item) for item in items],
        "jobs": [
            {
                "name": name,
                "help": spec.help,
                "default": name == config.project.default_job,
                "params": [
                    {
                        "name": key,
                        "type": param.type,
                        "required": param.required,
                        "choices": param.choices or [],
                        "help": param.help,
                    }
                    for key, param in spec.params.items()
                    if param.type != "secret"
                ],
            }
            for name, spec in config.jobs.items()
            if visible(spec.audience, role)
        ],
        "workflows": [
            {"name": name, "help": spec.help}
            for name, spec in config.workflows.items()
            if visible(spec.audience, role)
            and command_allowed("workflow", role, config.command_audience)
        ],
    }
