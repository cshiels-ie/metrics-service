#!/usr/bin/env bash
# Regenerate OpenAPI schema files and apply known manual patches.
#
# CI (pr-checks.yml) runs spectacular on Linux; local macOS generates slightly
# different output for untyped path params and some DAB-provided endpoints.
# This script regenerates both files and applies the patches needed to match CI.
#
# Usage (from repo root): bash tools/generate-openapi.sh
set -euo pipefail

YAML_OUT="tools/openapi-schema/metrics-service.yaml"
JSON_OUT="tools/openapi-schema/metrics-service.json"

mkdir -p tools/openapi-schema

echo "→ Generating YAML schema..."
uv run --frozen python manage.py spectacular --file "$YAML_OUT"

echo "→ Generating JSON schema..."
uv run --frozen python manage.py spectacular --format openapi-json --file "$JSON_OUT"

echo "→ Applying known manual patches..."
uv run --frozen python - <<'PYEOF'
import json, re, pathlib

# ── JSON patches ──────────────────────────────────────────────────────────────
# spectacular generates JSON with indent=4, no trailing newline.
# Patches are applied by loading, mutating, and writing back with the same format.
p = pathlib.Path("tools/openapi-schema/metrics-service.json")
data = json.loads(p.read_text())
paths = data["paths"]

# 1. Path param type: integer → string for viewsets where spectacular cannot
#    resolve the type from untyped URL patterns on the CI Linux environment.
for path, method in [
    ("/api/v1/dashboard_reports/report/{id}/", "get"),
    ("/api/v1/dashboard_reports/subscription_costs/{id}/", "put"),
    ("/api/v1/dashboard_reports/subscription_costs/{id}/", "patch"),
]:
    if path in paths and method in paths[path]:
        for param in paths[path][method].get("parameters", []):
            if param.get("name") == "id" and param.get("schema", {}).get("type") == "integer":
                param["schema"]["type"] = "string"
                param.pop("description", None)
                print(f"  [JSON] fixed path param type: {path} [{method}]")

# 2. Add /api/v1/feature_flags_state/ endpoint (added in DAB; absent on some envs)
flag_state_path = "/api/v1/feature_flags_state/"
if flag_state_path not in paths:
    entry = {"get": {
        "operationId": "feature_flags_state_retrieve",
        "description": "A view class for displaying feature flags",
        "tags": ["feature_flags_state"],
        "security": [{"cookieAuth": []}, {"basicAuth": []}],
        "responses": {"200": {
            "content": {"application/json": {
                "schema": {"type": "object", "additionalProperties": {}},
                "examples": {"Featureflags": {
                    "value": {"FLAG1": True, "FLAG2": False},
                    "summary": "featureflags"
                }}
            }},
            "description": ""
        }},
        "x-ai-description": "Retrieve single feature flags state"
    }}
    new_paths = {}
    for k, v in paths.items():
        new_paths[k] = v
        if k == "/api/v1/feature_flags/states/{id}/":
            new_paths[flag_state_path] = entry
    data["paths"] = paths = new_paths
    print("  [JSON] added feature_flags_state endpoint")

# 3. Teams org disassociation: remove requestBody, simplify 200 response
disassoc = "/api/v1/teams/{id}/organization/disassociate/"
if disassoc in paths:
    for method in ("post", "put", "patch"):
        if method in paths[disassoc]:
            op = paths[disassoc][method]
            if op.pop("requestBody", None):
                print(f"  [JSON] removed requestBody from {disassoc} [{method}]")
            if "200" in op.get("responses", {}):
                op["responses"]["200"] = {"description": "No response body"}
                print(f"  [JSON] simplified 200 response for {disassoc} [{method}]")

# 4. Remove OrganizationDisassociate component schemas (removed in DAB update)
for key in ["OrganizationDisassociate", "OrganizationDisassociateRequest"]:
    if data["components"]["schemas"].pop(key, None):
        print(f"  [JSON] removed schema: {key}")

# Write with spectacular's native format: indent=4, no trailing newline
p.write_text(json.dumps(data, indent=4))
print("JSON patches done.")

# ── YAML patches ──────────────────────────────────────────────────────────────
yp = pathlib.Path("tools/openapi-schema/metrics-service.yaml")
content = yp.read_text()

# 1. Path param type: integer → string for the specific operationIds where
#    spectacular cannot resolve the type on CI Linux (targeted, not global).
#    Only these 3 are affected; other Job Data endpoints stay as integer.
op_id_fixes = {
    "dashboard_reports_report_retrieve": "A unique integer value identifying this Job Data.",
    "dashboard_reports_subscription_costs_update": "A unique integer value identifying this Subscription Cost.",
    "dashboard_reports_subscription_costs_partial_update": "A unique integer value identifying this Subscription Cost.",
}
for op_id, desc in op_id_fixes.items():
    # Find the operationId, then patch the type: integer block after it
    idx = content.find(f"operationId: {op_id}")
    if idx == -1:
        continue
    old_block = (
        "        schema:\n          type: integer\n"
        f"        description: {desc}\n"
        "        required: true"
    )
    new_block = "        schema:\n          type: string\n        required: true"
    patch_idx = content.find(old_block, idx)
    if patch_idx != -1:
        content = content[:patch_idx] + new_block + content[patch_idx + len(old_block):]
        print(f"  [YAML] fixed path param type: {op_id}")

# 2. Add feature_flags_state endpoint — insert immediately before /api/v1/organizations/
if "/api/v1/feature_flags_state/" not in content:
    new_block = (
        "  /api/v1/feature_flags_state/:\n"
        "    get:\n"
        "      operationId: feature_flags_state_retrieve\n"
        "      description: A view class for displaying feature flags\n"
        "      tags:\n"
        "      - feature_flags_state\n"
        "      security:\n"
        "      - cookieAuth: []\n"
        "      - basicAuth: []\n"
        "      responses:\n"
        "        '200':\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                type: object\n"
        "                additionalProperties: {}\n"
        "              examples:\n"
        "                Featureflags:\n"
        "                  value:\n"
        "                    FLAG1: true\n"
        "                    FLAG2: false\n"
        "                  summary: featureflags\n"
        "          description: ''\n"
        "      x-ai-description: Retrieve single feature flags state\n"
    )
    trigger = "  /api/v1/organizations/:\n"
    idx = content.find(trigger)
    if idx != -1:
        content = content[:idx] + new_block + content[idx:]
        print("  [YAML] added feature_flags_state endpoint")
    else:
        print("  [YAML] WARNING: could not find /api/v1/organizations/ anchor")

# 3. Remove requestBody from teams org disassociation
rb_pattern = (
    r"      requestBody:\n"
    r"        content:\n"
    r"          application/json:\n"
    r"            schema:\n"
    r"              \$ref: '#/components/schemas/OrganizationDisassociateRequest'\n"
    r"          application/x-www-form-urlencoded:\n"
    r"            schema:\n"
    r"              \$ref: '#/components/schemas/OrganizationDisassociateRequest'\n"
    r"          multipart/form-data:\n"
    r"            schema:\n"
    r"              \$ref: '#/components/schemas/OrganizationDisassociateRequest'\n"
    r"        required: true\n"
)
content, n = re.subn(rb_pattern, "", content)
if n:
    print(f"  [YAML] removed requestBody from org disassociation ({n})")

resp_pattern = (
    r"(        '200':\n)"
    r"          content:\n"
    r"            application/json:\n"
    r"              schema:\n"
    r"                \$ref: '#/components/schemas/OrganizationDisassociate'\n"
    r"          description: ''\n"
    r"(      x-ai-description: Disassociate organization from a team)"
)
content, n = re.subn(resp_pattern, r"\1          description: No response body\n\2", content)
if n:
    print(f"  [YAML] fixed 200 response for org disassociation ({n})")

# 4. Remove OrganizationDisassociate component schemas
schemas_pattern = (
    r"    OrganizationDisassociate:\n"
    r"      type: object\n"
    r"      description: Serializer used for removing objects that are currently associated\n"
    r"        via a many-to-many relationship\n"
    r"      properties:\n"
    r"        instances:\n"
    r"          type: array\n"
    r"          items:\n"
    r"            type: integer\n"
    r"          description: A list of organizations to remove from this relationship\.\n"
    r"      required:\n"
    r"      - instances\n"
    r"    OrganizationDisassociateRequest:\n"
    r"      type: object\n"
    r"      description: Serializer used for removing objects that are currently associated\n"
    r"        via a many-to-many relationship\n"
    r"      properties:\n"
    r"        instances:\n"
    r"          type: array\n"
    r"          items:\n"
    r"            type: integer\n"
    r"          description: A list of organizations to remove from this relationship\.\n"
    r"      required:\n"
    r"      - instances\n"
)
content, n = re.subn(schemas_pattern, "", content)
if n:
    print(f"  [YAML] removed OrganizationDisassociate schemas ({n})")

yp.write_text(content)
print("YAML patches done.")
PYEOF

echo ""
echo "Done. Review:"
echo "  git diff $YAML_OUT"
echo "  git diff $JSON_OUT"
echo ""
echo "Commit both files if the diff looks correct."
