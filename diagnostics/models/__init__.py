# diagnostics/models/__init__.py
from .core_models import DiagnosticSession, DiagnosticMetric
from .sport_specific import WrestlingSpecificMetric
from .registry import register_metric, get_metric, list_registered_metrics

__all__ = [
    "DiagnosticSession",
    "DiagnosticMetric",
    "WrestlingSpecificMetric",
    "register_metric",
    "get_metric",
    "list_registered_metrics",
]
