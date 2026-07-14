"""gendoc - Pipeline de documentation graphique automatique pour projet Python.

Utilisation comme librairie:

    >>> import gendoc
    >>> pkg = gendoc.analyze_package("./mon_package")
    >>> gendoc.build_docs("./mon_package", output_dir="./site")
    >>> diags = gendoc.get_diagrams("./mon_package", "mermaid")

CLI:

    $ gendoc build ./mon_package
    $ gendoc check ./mon_package
"""

__version__ = "0.1.0"
__author__ = "Visual Doc Team"

from .analyzer import PackageInfo, analyze_package
from .builder import SiteBuilder
from .config import GendocConfig, load_config

# API haut niveau pour usage librairie
from .api import (
    analyze,
    build_docs,
    build_docs_with_config,
    check_package,
    get_diagrams,
    quick_overview,
)

__all__ = [
    # Core
    "analyze_package",
    "PackageInfo",
    "GendocConfig",
    "load_config",
    "SiteBuilder",
    # API librairie (haut niveau)
    "analyze",
    "build_docs",
    "build_docs_with_config",
    "get_diagrams",
    "check_package",
    "quick_overview",
]
