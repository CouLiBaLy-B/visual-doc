"""gendoc - Pipeline de documentation graphique automatique pour projet Python."""

__version__ = "0.1.0"
__author__ = "Visual Doc Team"

from .analyzer import analyze_package, PackageInfo
from .config import GendocConfig, load_config
from .builder import SiteBuilder

__all__ = ["analyze_package", "PackageInfo", "GendocConfig", "load_config", "SiteBuilder"]
