"""PTK documentation. Requirement conventions are declared here, never loaded from YAML."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "_ext"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "PTK"
author = "PTK contributors"
extensions = ["schema_reference", "diagram_assets", "sphinx_needs", "sphinx_design"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "sphinx_rtd_theme"
html_theme_options = {"navigation_depth": 3, "collapse_navigation": False}
html_static_path = ["_static"]
html_css_files = ["custom.css", "ptk-docs.css"]
html_title = "PTK documentation"
html_show_sourcelink = True

# This small, explicit subset follows the supplied requirements meta-model.
# The reference YAML and the legacy Sphinx configuration are not build inputs.
needs_types = [
    {
        "directive": "feature",
        "title": "Feature",
        "prefix": "FEAT_",
        "color": "#DCEAF7",
        "style": "node",
    },
    {
        "directive": "req-stkh",
        "title": "Stakeholder requirement",
        "prefix": "REQ_Stkh_",
        "color": "#DCEAF7",
        "style": "node",
    },
    {
        "directive": "req-sys",
        "title": "System requirement",
        "prefix": "REQ_Sys_",
        "color": "#E4EEDB",
        "style": "node",
    },
    {
        "directive": "req-sw",
        "title": "Software requirement",
        "prefix": "REQ_Sw_",
        "color": "#F5E8CE",
        "style": "node",
    },
]
needs_id_required = True
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_]*$"
needs_fields = {
    name: {"schema": {"type": "string"}}
    for name in (
        "req_type",
        "legal",
        "safety",
        "security",
        "status_crs",
        "safety_relevance",
        "verification_criteria",
        "verification_level",
    )
}
needs_fields["status"] = {
    "schema": {
        "type": "string",
        "enum": [
            "draft",
            "under review",
            "in clarification",
            "accepted",
            "rejected",
            "obsolete",
        ],
    }
}
needs_links = {
    "clustered_by": {"incoming": "Stakeholder requirements", "outgoing": "Feature"},
    "req_satisfies": {"incoming": "Satisfied by", "outgoing": "Satisfies"},
    "func_parent": {"incoming": "Child features", "outgoing": "Parent feature"},
}
needs_build_json = True
needs_table_style = "TABLE"
needs_table_classes = ["tight-table"]
