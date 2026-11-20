#!/usr/bin/env python3
"""Mide la longitud minificada de la politica ci-boundary.

Una managed policy de IAM admite 6.144 caracteres sin espacios (Design Decision 13
de bronze-silver). Uso:

    python3 scripts/policy_size.py infra/terraform/bootstrap/bootstrap.tfplan
    python3 scripts/policy_size.py --json plan.json
    python3 scripts/policy_size.py --policy-document document.json

El plan lo guarda el owner con `terraform plan -out=...`; este script solo lo lee
con `terraform -chdir=<carpeta del plan> show -json <plan>` (sin plan ni apply).
Con --json lee un plan ya exportado, sin ejecutar terraform. Con --policy-document
lee el Document de una PolicyVersion obtenido de AWS (JSON o URL-encoded), para
medir la politica ya aplicada.

Salida: la longitud minificada. Codigo 1 si es >= 6.144, 2 si no encuentra la politica.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.parse

ADDRESS = "aws_iam_policy.ci_boundary"
LIMIT = 6144


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(3)


def load_plan(args):
    if args.json:
        with open(args.json, encoding="utf-8") as fh:
            return json.load(fh)
    plan_path = os.path.abspath(args.plan)
    if not os.path.isfile(plan_path):
        fail(f"no existe el plan {args.plan}")
    directory, name = os.path.split(plan_path)
    try:
        result = subprocess.run(
            ["terraform", f"-chdir={directory}", "show", "-json", name],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        fail("no se encuentra el binario terraform en el PATH")
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        fail(
            f"terraform show -json {name} fallo (codigo {result.returncode}) en {directory}. "
            "Comprueba que la carpeta esta inicializada (terraform init) y que el plan es de ella."
        )
    return json.loads(result.stdout)


def load_policy_document(path):
    """Lee un Document de PolicyVersion; lo decodifica si viene URL-encoded."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    if not text.startswith(("{", "[")):
        text = urllib.parse.unquote(text)
    data = json.loads(text)
    # Tolera la respuesta completa de get-policy-version.
    if isinstance(data, dict) and "PolicyVersion" in data:
        data = data["PolicyVersion"]
    if isinstance(data, dict) and "Document" in data:
        data = data["Document"]
        if isinstance(data, str):
            data = json.loads(urllib.parse.unquote(data))
    return json.dumps(data)


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
    parser.add_argument(
        "--policy-document",
        help="Document de la PolicyVersion obtenido de AWS (JSON o URL-encoded)",
    )
    args = parser.parse_args()
    if sum(bool(x) for x in (args.plan, args.json, args.policy_document)) != 1:
        parser.error("indica solo uno: ruta del plan, --json o --policy-document")

    if args.policy_document:
        policy = load_policy_document(args.policy_document)
    else:
        policy = boundary_policy(load_plan(args))
    if policy is None:
        print(f"No hay {ADDRESS} en el plan", file=sys.stderr)
        return 2
    minified = json.dumps(json.loads(policy), separators=(",", ":"))
    print(f"ci-boundary: {len(minified)} caracteres minificados (limite {LIMIT})")
    return 1 if len(minified) >= LIMIT else 0


if __name__ == "__main__":
    sys.exit(main())
