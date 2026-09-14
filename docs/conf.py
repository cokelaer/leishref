# Configuration file for Sphinx documentation builder.

project = "leishref"
copyright = "2026"
author = "cokelaer"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = "logo.png"

autodoc_mock_imports = ["yaml", "click"]
