#!/usr/bin/env bash
# End-to-end demonstration of Noema's content-addressed composition.
#
# 1. Publish two classifier symbols to a scratch store.
# 2. Mint an index bundling those classifiers under stable names.
# 3. Write a consumer module that `from`-imports through the index.
# 4. Run the consumer.
#
# The point: agent A publishes classifiers, agent B assembles them, agent C
# consumes — and every reference between them is a content hash, not a name.
# No version drift, no "which version of lodash," no registry. The hash is
# the specification.

set -euo pipefail

cd "$(dirname "$0")/../.."

export NOEMA_STORE="$(mktemp -d)"
trap "rm -rf '$NOEMA_STORE'" EXIT

echo "=== 1. Publish classifiers to the store ==="
python3 -m noema store put examples/triage/classifier_sentiment.nm
python3 -m noema store put examples/triage/classifier_length.nm
echo

SENTIMENT_ID=$(python3 -m noema store hash examples/triage/classifier_sentiment.nm | awk '{print $1}')
LENGTH_ID=$(python3 -m noema store hash examples/triage/classifier_length.nm | awk '{print $1}')

echo "=== 2. Mint an index bundling both classifiers ==="
INDEX_LINE=$(python3 -m noema store index --name triage_lib \
    "classify_sentiment=$SENTIMENT_ID" \
    "classify_length=$LENGTH_ID")
echo "$INDEX_LINE"
INDEX_ID=$(echo "$INDEX_LINE" | awk '{print $1}')
echo

echo "=== 3. Write consumer importing through the index ==="
CONSUMER="$NOEMA_STORE/consumer.nm"
cat > "$CONSUMER" <<EOF
module consumer

from $INDEX_ID import classify_sentiment, classify_length

def route
  intent "demonstrate content-addressed composition via triage"
  sig    (msg: String) -> Decision
  effects {}
  cand
    s <- classify_sentiment(msg)
    believe s
      ge(conf(s), 0.85) => "confident-sentiment"
      else              => fallback(msg)

def fallback
  intent "escalate to length classifier when sentiment is uncertain"
  sig    (msg: String) -> Decision
  effects {}
  cand
    l <- classify_length(msg)
    believe l
      ge(conf(l), 0.90) => "confident-length"
      else              => bottom

def main
  intent "drive the consumer with a test message"
  sig    () -> Decision
  effects {}
  cand
    route("this is a great product")
EOF
cat "$CONSUMER"
echo

echo "=== 4. Run the consumer ==="
python3 -m noema run "$CONSUMER"
