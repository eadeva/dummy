import json
import logging
import os
import pathlib
import shutil
import sys
from pathlib import Path

# -- Path setup ---------------------------------------------------------------
CONF_DIR = Path(__file__).resolve().parent
REPO_DIR = CONF_DIR.parents[3]
DOCASCODE_DIR = CONF_DIR.parent
DOCS_DIR = REPO_DIR / "docs"


def conf_path(relative_path: str) -> pathlib.Path:
    return (DOCASCODE_DIR / relative_path).resolve()


def docs_path(relative_path: str) -> pathlib.Path:
    return (DOCS_DIR / relative_path).resolve()


def env_flag_enabled(var_name: str, default: bool = True) -> bool:
    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return default

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if normalized in {
        "",
        "0",
        "false",
        "no",
        "off",
        "none",
        "disable",
        "disabled",
    }:
        return False

    return default


def parse_bool_value(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if normalized in {
        "",
        "0",
        "false",
        "no",
        "off",
        "none",
        "disable",
        "disabled",
    }:
        return False

    return default


def resolve_repo_path(raw_path: str) -> pathlib.Path:
    candidate = pathlib.Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_DIR / candidate).resolve()


def parse_step_list(var_name: str) -> list[dict]:
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except Exception as exc:
        print(f"[WARNING] Invalid {var_name} payload. Expected JSON list. Error: {exc}")
        return []

    if not isinstance(parsed, list):
        print(f"[WARNING] {var_name} must be a JSON list. Ignoring value.")
        return []

    return [item for item in parsed if isinstance(item, dict)]


def build_default_visio_arch_files(
    out_folder: pathlib.Path, project_name: str
) -> list[str]:
    # arch2needs names its outputs per variant: <project>_<type>_needs.<variant>.json
    variant = os.environ.get("XC_CE_UTILS_VARIANT_ALIAS", "").strip()
    suffix = f".{variant}" if variant else ""
    return [
        str(out_folder / f"{project_name}_{object_type}_needs{suffix}.json")
        for object_type in (
            "SwComp",
            "SwCpt",
            "SysBuildingBlock",
            "Interface",
            "Connection",
        )
    ]


def move_docascode_logs_to_variant_action() -> None:
    """Move local docascode logs to _logs/<variant>/<action>."""
    variant_alias = os.environ.get("XC_CE_UTILS_VARIANT_ALIAS", "").strip()
    action_name = os.environ.get("XC_CE_UTILS_ACTION", "").strip()

    if not variant_alias:
        variant_alias = "default"
    if not action_name:
        action_name = "doc"

    destination_dir = REPO_DIR / "_logs" / variant_alias / action_name
    destination_dir.mkdir(parents=True, exist_ok=True)

    log_names = (
        "arch2needs.log",
        "architecture_validation.log",
        "architecture_validation.json",
        "ProcessVisioSvgs.log",
    )

    source_candidates: dict[str, pathlib.Path] = {}
    for log_name in log_names:
        conf_candidate = (CONF_DIR / log_name).resolve()
        cwd_candidate = (Path.cwd() / log_name).resolve()

        if conf_candidate.exists():
            source_candidates[log_name] = conf_candidate
        elif cwd_candidate.exists():
            source_candidates[log_name] = cwd_candidate

    if not source_candidates:
        return

    source_set = {
        os.path.normcase(str(path.resolve())) for path in source_candidates.values()
    }

    # Close matching file handlers to avoid Windows file locks while moving logs.
    logger_objects = [logging.getLogger()]
    logger_objects.extend(
        logger
        for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    )

    for logger in logger_objects:
        for handler in list(logger.handlers):
            if not isinstance(handler, logging.FileHandler):
                continue

            handler_path = Path(getattr(handler, "baseFilename", "")).resolve()
            if os.path.normcase(str(handler_path)) not in source_set:
                continue

            try:
                handler.flush()
                handler.close()
            finally:
                logger.removeHandler(handler)

    for log_name, source_path in source_candidates.items():
        destination_path = destination_dir / log_name
        if destination_path.exists():
            destination_path.unlink()

        shutil.move(str(source_path), str(destination_path))
        print(f"[INFO] Moved {log_name} to {destination_path}")


sys.path.append(str(REPO_DIR))

# -- Importing standard/project tooling --------------------------------------
from xc_ce_utils.core_engine.domain.runtime_context import get_runtime_context
from xc_ce_utils.docascode.conf_standard import *
from xc_ce_utils.docascode.conf_standard import setup as conf_standard_setup
from xc_ce_utils.docascode.generate_needs import generate_sphinx_needs_from_config
from xc_ce_utils.docascode.processVisioSVG import processAllVisioSVGs

# -- Sphinx configuration -----------------------------------------------------
project = os.environ.get(
    "PROJECT_NAME",
    os.environ.get("XC_CE_UTILS_ARTIFACT", "TOYOTA_CGW"),
).upper()
copyright = "Robert Bosch GmbH"
author = "XC-CE/EF2"
version = os.environ.get("RB_VERSION", "")
html_title = " ".join(
    part
    for part in (
        project,
        os.environ.get("XC_CE_UTILS_VARIANT_ALIAS", "").strip(),
        version,
    )
    if part
)
SCHEMA_VERSION = globals().get("__SCHEMA_VERSION__", "25.22")

master_doc = "index"

# -- Sphinx-Needs auto generation scripts ------------------------------------
out_folder: pathlib.Path = docs_path("_gen_needs")
if not out_folder.exists():
    out_folder.mkdir(parents=True)

# -- Processing of Visio SVG files -------------------------------------------
pre_build_steps = parse_step_list("XC_CE_UTILS_PRE_BUILD_STEPS")
needs_generation_ran = False

for step in pre_build_steps:
    step_name = str(step.get("name", "")).strip().lower()
    if not step_name:
        continue

    if not parse_bool_value(step.get("enabled", True), True):
        print(f"[INFO] Skipping pre-build step '{step_name}' because it is disabled")
        continue

    if step_name == "generate_sphinx_needs":
        config_entry = step.get("config")
        if not isinstance(config_entry, str) or not config_entry.strip():
            print(
                "[WARNING] Skipping generate_sphinx_needs because no config path was provided"
            )
            continue

        config_path = resolve_repo_path(config_entry)
        try:
            needs_generation_config = generate_sphinx_needs_from_config(
                config_path,
                REPO_DIR,
                project=project,
                project_needs_config=CONF_DIR / "needs_config.yml",
            )
        finally:
            # also on a failed generation, so its logs end up in _logs
            move_docascode_logs_to_variant_action()
        out_folder = needs_generation_config.output_dir
        needs_generation_ran = True
        continue

    if step_name in {"process_visio_svgs", "process_visio_svg"}:
        if not needs_generation_ran:
            print(
                "[INFO] Skipping processAllVisioSVGs because generate_sphinx_needs did not run in this build"
            )
            continue

        raw_arch_file_names = step.get("archFileNames")
        if isinstance(raw_arch_file_names, list) and raw_arch_file_names:
            arch_file_names = [
                str(resolve_repo_path(item))
                for item in raw_arch_file_names
                if isinstance(item, str) and item.strip()
            ]
        else:
            arch_file_names = build_default_visio_arch_files(out_folder, project)

        svgs_in_folder = step.get(
            "svgsInFolder",
            "build_environment/xc-ce-utils/docascode/sphinx/svgs",
        )
        svgs_out_folder = step.get("svgsOutFolder", "docs/_svgsOut")
        needs_path = step.get("needsPath", "../gen_needs.html")

        processAllVisioSVGs(
            archFileNames=arch_file_names,
            outFolder=str(out_folder),
            svgsInFolder=str(resolve_repo_path(str(svgs_in_folder))),
            svgsOutFolder=str(resolve_repo_path(str(svgs_out_folder))),
            needs_path=str(needs_path),
        )
        continue

    print(f"[WARNING] Unknown pre-build step '{step_name}'. Skipping.")

move_docascode_logs_to_variant_action()

needs_title_optional = True
needs_title_from_content = False

exclude_patterns = [
    f"{os.environ.get('SPHINX_BUILD_FOLDER', '_builds')}/*",
    "_builds",
    "venv",
    "ref_arch",
    "codebase",
    "productlines/bsw_kit",
    "_tools",
    "taco",
    "req_viewpoint/07_req/SafEx/sw/03_req-sw_SafEx/Abbreviations/03_req-sw_SafEx_Abbreviations_index.rst",
    "**/*.md",
    "**/architecture_needs.md",
    "**/usage_of_requirements.md",
]

needs_yaml_log_folder = os.environ.get("LOGS_FOLDER", str(CONF_DIR))

# -- Options for plantUML usage ----------------------------------------------
plantuml_output_format = "svg_img"
plantuml_batch_size = 100

# The needs builder renders no diagrams, so a missing jar is only a warning there
needs_only_build = os.environ.get("XC_CE_UTILS_DOCS_BUILDER", "").strip() == "needs"

plantuml_jar = (
    os.environ.get("SPHINX_PLANTUML_JAR", "").strip()
    or os.environ.get("PLANTUML_JAR", "").strip()
)
plantuml_jar_error = ""
if not plantuml_jar:
    plantuml_jar_error = "PLANTUML_JAR or SPHINX_PLANTUML_JAR is not set. Please configure the PlantUML jar path."
    plantuml_jar_path = Path("plantuml.jar")
else:
    plantuml_jar_path = resolve_repo_path(plantuml_jar)
    if not plantuml_jar_path.exists():
        plantuml_jar_error = (
            f"Configured PlantUML jar does not exist: {plantuml_jar_path}. "
            "Set PLANTUML_JAR or SPHINX_PLANTUML_JAR to a valid path."
        )

if plantuml_jar_error:
    if not needs_only_build:
        raise Exception(plantuml_jar_error)
    print(f"[WARNING] {plantuml_jar_error} Not needed for the needs builder.")

architecture_includes = conf_path(
    "infrastructure/architecture/99_Infrastructure/ConstructionKit/Includes"
)
plantuml = (
    f'java -Dplantuml.include.path="{architecture_includes.as_posix()}" '
    f'-jar "{plantuml_jar_path.as_posix()}"'
)

# -- Breathe configuration ----------------------------------------------------
doxygen_build_folder = os.environ.get("DOXYGEN_BUILD_FOLDER", "").strip()
if not doxygen_build_folder:
    raise Exception(
        "DOXYGEN_BUILD_FOLDER is not set. Please configure the Doxygen output folder path."
    )

breathe_projects = {project: doxygen_build_folder}
breathe_default_project = project
breathe_domain_by_extension = {
    "h": "c",
    "c": "c",
}

runtime_context = get_runtime_context()
skip_doxygen = env_flag_enabled("XC_CE_UTILS_SKIP_DOXYGEN", default=False)
if runtime_context.is_docker and skip_doxygen:
    warnings_list = globals().get("suppress_warnings")
    if warnings_list is None:
        warnings_list = []
        globals()["suppress_warnings"] = warnings_list
    if "breathe" not in warnings_list:
        warnings_list.append("breathe")
    print(
        "[INFO] Docker runtime detected with XC_CE_UTILS_SKIP_DOXYGEN enabled. "
        "Breathe warnings are suppressed because Doxygen XML generation was intentionally skipped."
    )

# -- General options ----------------------------------------------------------
todo_include_todos = True
latex_engine = "pdflatex"

# -- TACO test catalog (generated by the xc-ce-utils taco_catalog extension) --
taco_tc_dirs = [
    REPO_DIR / "vnv",
    REPO_DIR / "sw_composition",
]
taco_tc_output = str(DOCS_DIR / "taco")
taco_tc_template_dir = str(REPO_DIR / "test" / "templates")
taco_tc_template_mapping = {
    "robot": {"output_file": "robot_tests.rst"},
    "cpp": {"output_file": "google_tests.rst"},
}
# Test management: test selections (.tl.yaml) and test suites (.ts.yaml)
taco_tm_dir = [REPO_DIR / "test" / "management"]


def setup(app):
    conf_standard_setup(app)
