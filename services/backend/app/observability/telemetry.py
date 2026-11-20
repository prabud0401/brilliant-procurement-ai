"""OpenTelemetry configuration with Azure Monitor distro and graceful fallback."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from app.core.config import settings

logger = logging.getLogger("app.observability.telemetry")

_telemetry_initialized = False


class _NoOpSpan:
    """Fallback no-op span context manager when OpenTelemetry is inactive."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass


class _NoOpTracer:
    """Fallback no-op tracer."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Generator[_NoOpSpan, None, None]:
        span = _NoOpSpan()
        yield span


def setup_telemetry(service_name: str = "backend") -> bool:
    """Initialize OpenTelemetry with Azure Monitor distro if connection string is configured.

    Falls back to console exporter if OTEL_DEBUG is enabled, or no-op otherwise.
    Never raises an exception, ensuring zero hard runtime dependencies.
    """
    global _telemetry_initialized
    if _telemetry_initialized:
        return True

    conn_str = settings.APPLICATIONINSIGHTS_CONNECTION_STRING
    otel_debug_val = str(settings.OTEL_DEBUG).strip().lower()
    otel_debug = bool(settings.OTEL_DEBUG and otel_debug_val not in ("0", "false"))

    if conn_str:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore[import-untyped]

            configure_azure_monitor(
                connection_string=conn_str,
                service_name=service_name,
            )
            _telemetry_initialized = True
            logger.info("Configured Azure Monitor OpenTelemetry for %s", service_name)
            return True
        except ImportError:
            logger.warning("azure-monitor-opentelemetry not installed. Telemetry export disabled.")
        except Exception as exc:
            logger.warning("Failed to initialize Azure Monitor OpenTelemetry: %s", exc)

    if otel_debug:
        logger.info("OTEL_DEBUG active: Running OpenTelemetry in debug mode (no-op/console)")
        _telemetry_initialized = True
        return True

    logger.debug("OpenTelemetry inactive (no APPLICATIONINSIGHTS_CONNECTION_STRING configured)")
    return False


def get_tracer(name: str = "pda") -> Any:
    """Return an OpenTelemetry tracer if available, otherwise return a no-op tracer."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()
