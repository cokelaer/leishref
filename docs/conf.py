# Configuration file for Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "leishref"
copyright = "2026"
author = "cokelaer"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = ".rst"
master_doc = "index"

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = "logo.png"

autodoc_mock_imports = ["yaml", "click", "rich_click", "bioservices", "requests"]
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "undoc-members": False,
    "show-inheritance": True,
}

napoleon_include_init_with_doc = False
napoleon_use_rtype = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
