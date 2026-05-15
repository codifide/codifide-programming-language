#!/usr/bin/env bash
# Seed the public Codifide registry with the five canonical pipeline symbols.
#
# Usage:
#   ./scripts/seed_registry.sh [--registry https://registry.codifide.com]
#
# Prerequisites:
#   - The pipeline programs must be stored locally:
#       python3 -m codifide store put content_classifier.cod
#       python3 -m codifide store put moderation_gate.cod
#       python3 -m codifide store put escalation_router.cod
#   - The registry must be running and reachable.
#
# The five canonical hashes (from the v4.0 session):
#   classify_content  sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae
#   moderate          sha256:1bbe69ba7dae84a1fc1a5b335ac2fd9f4be3e4462857db3cc0d38c4af5be4a2a
#   route_message     sha256:68c15e1108ac195e211634d2755f58353422db61b077690ec59686ad87d2d964

set -euo pipefail

REGISTRY="${1:---registry}"
if [ "$REGISTRY" = "--registry" ]; then
    REGISTRY_URL="${2:-https://registry.codifide.com}"
else
    REGISTRY_URL="$REGISTRY"
fi

echo "Seeding registry: $REGISTRY_URL"
echo ""

HASHES=(
    "sha256:377099c5bddb8cebe9e8bc6b8499bb00ea99083798d1b064799ac82c55636fae"
    "sha256:1bbe69ba7dae84a1fc1a5b335ac2fd9f4be3e4462857db3cc0d38c4af5be4a2a"
    "sha256:68c15e1108ac195e211634d2755f58353422db61b077690ec59686ad87d2d964"
)

NAMES=(
    "classify_content"
    "moderate"
    "route_message"
)

for i in "${!HASHES[@]}"; do
    hash="${HASHES[$i]}"
    name="${NAMES[$i]}"
    echo -n "  pushing $name ($hash)... "
    python3 -m codifide store push "$hash" --registry "$REGISTRY_URL" && echo "ok" || echo "FAILED"
done

echo ""
echo "Verifying..."
for i in "${!HASHES[@]}"; do
    hash="${HASHES[$i]}"
    name="${NAMES[$i]}"
    echo -n "  $name: "
    curl -sf --max-time 10 \
        -H "Accept: application/json" \
        "$REGISTRY_URL/symbols/$hash" > /dev/null \
        && echo "reachable" \
        || echo "NOT FOUND"
done

echo ""
echo "Done. Test with:"
echo "  python3 -m codifide run pipeline_composed.cod --registry $REGISTRY_URL"
