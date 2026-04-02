#!/usr/bin/env bash
# propose-commit.sh — propose then commit a DataDictionary entry in one shot.
#
# Usage:
#   ./scripts/propose-commit.sh "customerId is a UUID v4 identifier..."
#   FUNCTION=data-dictionary-mcp-dev ./scripts/propose-commit.sh "..."
#
set -euo pipefail

PROMPT="${1:?Usage: $0 <prompt>}"
FUNCTION="${FUNCTION:-data-dictionary-mcp-prod}"
REGION="${AWS_REGION:-us-east-1}"
SESSION="${MCP_SESSION:-$(uuidgen | tr '[:upper:]' '[:lower:]')}"
TMPDIR_LOCAL="$(mktemp -d)"

# ---- helpers ----------------------------------------------------------------

invoke() {
  local method="$1" id="$2" params="$3" out="$TMPDIR_LOCAL/resp_${id}.json"
  local body
  body=$(jq -nc --arg m "$method" --arg id "$id" --argjson p "$params" \
    '{"jsonrpc":"2.0","id":($id|tonumber),"method":$m,"params":$p}')

  local payload
  payload=$(jq -nc \
    --arg body "$body" \
    --arg session "$SESSION" \
    '{
      "version": "2.0",
      "routeKey": "$default",
      "rawPath": "/mcp",
      "rawQueryString": "",
      "headers": {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "mcp-session-id": $session
      },
      "requestContext": {
        "accountId": "anonymous",
        "apiId": "lambda-url",
        "http": {"method": "POST", "path": "/mcp", "protocol": "HTTP/1.1",
                  "sourceIp": "127.0.0.1", "userAgent": "propose-commit-script"},
        "requestId": "script-invoke",
        "routeKey": "$default",
        "stage": "$default"
      },
      "isBase64Encoded": false,
      "body": $body
    }')

  aws lambda invoke \
    --function-name "$FUNCTION" \
    --region "$REGION" \
    --cli-binary-format raw-in-base64-out \
    --payload "$payload" \
    "$out" >/dev/null

  # SSE body: "event: message\r\ndata: <JSON>\r\n\r\n"
  # Extract the JSON on the data: line, then pull result.structuredContent.
  jq -r '.body' "$out" \
    | grep -o 'data: {.*' \
    | sed 's/^data: //' \
    | tr -d '\r' \
    | jq '.result.structuredContent'
}

# ---- step 1: propose --------------------------------------------------------

echo "⟳ Proposing..."
PROPOSE_RESULT=$(invoke "tools/call" 1 \
  "$(jq -nc --arg prompt "$PROMPT" \
    '{"name":"propose_data_element","arguments":{"prompt":$prompt}}')")

STATUS=$(echo "$PROPOSE_RESULT" | jq -r '.status')
PROPOSAL_ID=$(echo "$PROPOSE_RESULT" | jq -r '.proposal_id')
COMMIT_TOKEN=$(echo "$PROPOSE_RESULT" | jq -r '.commit_token // empty')

echo "  status      : $STATUS"
echo "  proposal_id : $PROPOSAL_ID"

if [[ "$STATUS" != "allowed" ]]; then
  SCORE=$(echo "$PROPOSE_RESULT" | jq -r '.signals.output_instability // "n/a"')
  echo ""
  echo "✗ Proposal blocked (output_instability=$SCORE)."
  echo "  Set OBSERVATORY_BLOCK_THRESHOLD=1.0 on the Lambda to bypass, then retry:"
  echo ""
  echo "  aws lambda update-function-configuration \\"
  echo "    --function-name $FUNCTION \\"
  echo "    --environment 'Variables={OBSERVATORY_BLOCK_THRESHOLD=1.0}'"
  exit 1
fi

# ---- step 2: commit ---------------------------------------------------------

echo "⟳ Committing..."
COMMIT_RESULT=$(invoke "tools/call" 2 \
  "$(jq -nc --arg pid "$PROPOSAL_ID" --arg tok "$COMMIT_TOKEN" \
    '{"name":"commit_data_element","arguments":{"proposal_id":$pid,"commit_token":$tok}}')")

echo ""
echo "✓ Done:"
echo "$COMMIT_RESULT" | jq .

rm -rf "$TMPDIR_LOCAL"
