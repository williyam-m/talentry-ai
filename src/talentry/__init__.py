"""Talentry AI — intelligent candidate discovery and ranking."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("talentry-ai")
except PackageNotFoundError:  # pragma: no cover - editable install fallback
    __version__ = "1.0.0"

__all__ = ["__version__"]
