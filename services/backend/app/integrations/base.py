"""Base classes and exceptions for external integrations."""

from __future__ import annotations


class IntegrationError(Exception):
    """Base exception for integration errors."""


class NotConfiguredError(IntegrationError):
    """Raised when an unconfigured or unimplemented integration adapter is invoked."""

    def __init__(
        self,
        message: str = "Real adapter is not configured. Set INTEGRATIONS_MODE=mock for local/test runs.",
    ) -> None:
        super().__init__(message)
