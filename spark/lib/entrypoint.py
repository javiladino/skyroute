"""Salida de los entrypoints de job compatible con Glue.

El ProcessLauncher de Glue ejecuta el script con runpy y trata cualquier SystemExit, incluso con
codigo 0, como fallo del run. `exit_on_error` solo sale cuando el codigo es distinto de cero.
"""

import sys


def exit_on_error(rc: int | None) -> None:
    """Llama a `sys.exit(rc)` solo si `rc` es truthy; con 0 o None vuelve sin lanzar nada."""
    if rc:
        sys.exit(rc)
