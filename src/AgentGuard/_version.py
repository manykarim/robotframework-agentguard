"""Version sourced from package metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("robotframework-agentguard")
except PackageNotFoundError:  # editable / pre-install
    __version__ = "0.2.1+dev"
