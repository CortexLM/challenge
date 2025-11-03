"""Configuration settings for challenge SDK."""

from dataclasses import dataclass


@dataclass
class Settings:
    """Simple settings class for SDK configuration.

    Currently minimal, can be extended as needed.
    """

    def __init__(self):
        """Initialize with defaults."""
