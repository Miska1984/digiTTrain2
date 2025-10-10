 # metrika regisztrációs és discovery mechanizmus
# diagnostics/models/registry.py
METRIC_REGISTRY = {}

def register_metric(category, name, calculator):
    METRIC_REGISTRY[f"{category}.{name}"] = calculator

def get_metric(category, name):
    return METRIC_REGISTRY.get(f"{category}.{name}")

def list_registered_metrics():
    return list(METRIC_REGISTRY.keys())
