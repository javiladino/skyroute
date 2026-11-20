#!/usr/bin/env python3
"""Mide la longitud minificada de la politica ci-boundary de un plan de bootstrap.

Una managed policy de IAM admite 6.144 caracteres sin espacios (Design Decision 13
de bronze-silver). Uso:

    python3 scripts/policy_size.py infra/terraform/bootstrap/bootstrap.tfplan
    python3 scripts/policy_size.py --json plan.json

El plan lo guarda el owner con `terraform plan -out=...`; este script solo lo lee
con `terraform show -json` (sin plan ni apply). Con --json lee un plan ya
exportado, sin ejecutar terraform.

Salida: la longitud minificada. Codigo 1 si es >= 6.144, 2 si no encuentra la politica.
"""

import argparse
import json
import subprocess
import sys

ADDRESS = "aws_iam_policy.ci_boundary"
LIMIT = 6144


def load_plan(args):
    if args.json:
        with open(args.json, encoding="utf-8") as fh:
            return json.load(fh)
    result = subprocess.run(
        ["terraform", "show", "-json", args.plan],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def boundary_policy(plan):
    """Devuelve el documento de la ci-boundary tras aplicar el plan (o el state previo)."""
    for change in plan.get("resource_changes", []):
        if change.get("address") == ADDRESS:
            after = (change.get("change") or {}).get("after") or {}
            if after.get("policy"):
                return after["policy"]
    values = (plan.get("prior_state") or {}).get("values", {})
    stack = [values.get("root_module", {})]
    while stack:
        module = stack.pop()
        for resource in module.get("resources", []):
            if resource.get("address") == ADDRESS:
                return resource["values"]["policy"]
        stack.extend(module.get("child_modules", []))
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", nargs="?", help="ruta del plan guardado (.tfplan)")
    parser.add_argument("--json", help="plan ya exportado con terraform show -json")
    args = parser.parse_args()
    if bool(args.plan) == bool(args.json):
        parser.error("indica la ruta del plan o --json, no ambos")

    policy = boundary_policy(load_plan(args))
    if policy is None:
        print(f"No hay {ADDRESS} en el plan", file=sys.stderr)
        return 2
    minified = json.dumps(json.loads(policy), separators=(",", ":"))
    print(f"ci-boundary: {len(minified)} caracteres minificados (limite {LIMIT})")
    return 1 if len(minified) >= LIMIT else 0


if __name__ == "__main__":
    sys.exit(main())
