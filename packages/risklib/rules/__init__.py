from __future__ import annotations

import importlib
import pkgutil
from typing import Callable

from packages.core.schemas.chart import PatientChart


def discover_rules() -> dict[str, Callable[[PatientChart], list]]:
    """Discover rule runners in this package."""
    runners: dict[str, Callable[[PatientChart], list]] = {}
    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda info: info.name):
        module_name = module_info.name
        module = importlib.import_module(f"{__name__}.{module_name}")
        runner = getattr(module, "run", None)
        if not callable(runner):
            raise RuntimeError(f"Rule module {module_name} has no run()")
        runners[module_name] = runner
    return runners


__all__ = ["discover_rules"]