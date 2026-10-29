## !!!! DO NOT MODIFY THIS FILE

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------
import pathlib
import sys

from sphinx_needs.api import add_dynamic_function

this_folder = pathlib.Path(__file__).parent
sys.path.insert(0, pathlib.Path(this_folder, "extensions").as_posix())

# -- Patch sphinx_needs to suppress matplotlib warning in PyInstaller bundles ------
# The standard suppress_warnings config doesn't work for directive-level warnings in Sphinx 9.x
import sphinx_needs.logging
from GTest_helpers import FindGTestCoverage, FindGTestResult
from meta_information_reader import get_meta_data_from_file

if hasattr(sphinx_needs.logging, "log_warning"):
    _original_log_warning = sphinx_needs.logging.log_warning

    def _patched_log_warning(
        logger,
        message,
        subtype,
        /,
        location,
        *,
        color=None,
        once=False,
        type="needs",
    ):
        """Patched log_warning that skips matplotlib warnings"""
        if subtype != "mpl":  # Skip matplotlib warnings
            _original_log_warning(
                logger,
                message,
                subtype,
                location,
                color=color,
                once=once,
                type=type,
            )

    sphinx_needs.logging.log_warning = _patched_log_warning

# -- Template information - version aligned with devops library release ------
__SCHEMA_VERSION__ = "25.22"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.

extensions = [
    "sphinxcontrib.plantuml",
    "sphinx_needs",
    "breathe",
    "sphinx.ext.todo",
    "myst_parser",  # Add MyST parser for Markdown support
    "archuml",
    "functree",
    "meta_model",
    "needs_yaml_loader",  # Load sphinx-needs config from YAML files
    "meta_model_validation",  # Meta model report (meta_model_validation_enabled = True)
    "verdict_overlay",  # TACO verdicts onto test cases (TACO_RESULTS_DIR)
    "taco_catalog",  # TACO test catalog from test sources (taco_tc_* in conf.py)
    "yaml_rst_parser",  # include-yaml-rst: test plans/suites from TACO .tl.yaml/.ts.yaml
    "ssl_inheritance",  # Inherit safety/security/legal onto test cases
    "sphinx_design",  # Grid layout for side-by-side content
    "sphinx.ext.ifconfig",  # Content depending on config values, e.g. the variant
    "variant_handling",  # Variant of the build: config values, tag, excludes, needs filter/variants
]

# -- MyST Parser Configuration -----------------------------------------------

# Configure MyST parser to support Markdown files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# MyST parser options
myst_enable_extensions = [
    "colon_fence",  # Support for ::: code fences
    "deflist",  # Definition lists
    "html_image",  # HTML image tags
    "linkify",  # Auto-convert URLs to links
    "replacements",  # Text replacements like (c) -> ©
    "smartquotes",  # Smart quotes
    "substitution",  # Variable substitutions
    "tasklist",  # Task lists with checkboxes
]

# Configure how MyST handles various elements
myst_heading_anchors = 3  # Generate anchors for headings up to level 3
myst_html_meta = {
    "description lang=en": "XC-CE Utils Documentation",
    "keywords": "bosch, automotive, embedded, documentation",
}

# Add any paths that contain templates here, relative to this directory.
# templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = [pathlib.Path(this_folder, "_custom").as_posix()]
needs_template_folder = pathlib.Path(this_folder, "_custom").as_posix()
# Custom formatting
html_css_files = ["custom.css"]

language = "en"

# FIXME - Commented out as RST preview does not work with this option and HTML looks bad
# Use svg as plantuml output
# plantuml_output_format = "svg"

# -- Sphinx-needs configuration ---------------------------------------------------
# All declarative sphinx-needs configuration (types, fields, links, constraints)
# is now loaded from YAML by the needs_yaml_loader extension.
#
# Generated:      PMT meta model + <project>/.../sphinx/meta_model_deviations.yaml (optional)
# Base config:    xc_ce_utils/docascode/needs_config.yml  (shipped with package)
# Project config: <project>/config/docascode/sphinx/needs_config.yml  (optional additions)
#
# See needs_yaml_loader extension for merge strategy documentation.


# definition of dynamic functions
def setup(app):
    add_dynamic_function(app, FindGTestResult)
    add_dynamic_function(app, FindGTestCoverage)
    add_dynamic_function(app, get_meta_data_from_file)
    app.add_config_value("rbd_meta_data_files", [], "env")
    app.add_config_value("rbd_gtest_report_dir", "", "env")
    app.add_config_value(
        "rbd_gtest_suite_separator",
        ["TC_SwC_", "TC_SwU_", "TST_SwC_", "TST_SwU_"],
        "env",
    )
    app.add_config_value("rbd_gtest_testcase_separator", "@", "env")
    app.add_config_value("rbd_docs_as_code_dynamic_functions_debug", False, "env")
