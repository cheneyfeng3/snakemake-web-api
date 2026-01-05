#!/bin/bash
set -e # Exit on error
unset http_proxy https_proxy # Bypass proxy for localhost connections

# --- Configuration ---
API_SERVER_URL="http://127.0.0.1:8082"
MAX_ATTEMPTS=600 # Long timeout for bioinfo workflows
WORKFLOW_ID=${1:-"rna-seq-star-deseq2"}
FIXED_JOB_ID=${2:-""}

echo "--- Step 1: Fetching demo case for $WORKFLOW_ID ---"
DEMO_RESPONSE=$(curl -s "$API_SERVER_URL/demos/workflows/$WORKFLOW_ID")

if [ $? -ne 0 ]; then
    echo "Error: Failed to connect to API server at $API_SERVER_URL."
    exit 1
fi

if [ "$(echo "$DEMO_RESPONSE" | jq -r 'type')" != "array" ] || [ "$(echo "$DEMO_RESPONSE" | jq 'length')" -eq 0 ]; then
    echo "Error: No demos found for $WORKFLOW_ID."
    echo "$DEMO_RESPONSE"
    exit 1
fi

DEMO_CASE=$(echo "$DEMO_RESPONSE" | jq '.[0]')
DEMO_CONFIG=$(echo "$DEMO_CASE" | jq '.config')

# Construct payload
SUBMIT_PAYLOAD=$(jq -n \
                  --arg wid "$WORKFLOW_ID" \
                  --argjson cfg "$DEMO_CONFIG" \
                  --arg jid "$FIXED_JOB_ID" \
                  '{workflow_id: $wid, config: $cfg, job_id: (if $jid != "" then $jid else null end)}')

echo "Payload to be submitted:"
echo "$SUBMIT_PAYLOAD" | jq .
echo ""

echo "--- Step 2: Submitting the workflow job ---"
HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_SERVER_URL/workflow-processes" \
     -H "Content-Type: application/json" \
     -d "$SUBMIT_PAYLOAD")

RESPONSE=$(echo "$HTTP_RESPONSE" | sed '$d')
HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 300 ]; then
    echo "Error: Server returned HTTP $HTTP_CODE"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "Response from server:"
echo "$RESPONSE" | jq .
echo ""

JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id')
STATUS_URL_PATH=$(echo "$RESPONSE" | jq -r '.status_url')
LOG_URL_PATH=$(echo "$RESPONSE" | jq -r '.log_url')

STATUS_URL="$API_SERVER_URL$STATUS_URL_PATH"
LOG_URL="$API_SERVER_URL$LOG_URL_PATH"

echo "Job ID: $JOB_ID"
echo "Status URL: $STATUS_URL"
echo "Log URL: $LOG_URL"
echo ""

echo "--- Step 4: Polling job status ---"
for ((i=1; i<=MAX_ATTEMPTS; i++)); do
    echo "Polling job status... Attempt $i of $MAX_ATTEMPTS"
    echo "You can view real-time logs at: $LOG_URL"
    
    JOB_STATUS_RESPONSE=$(curl -s "$STATUS_URL")
    CURRENT_STATUS=$(echo "$JOB_STATUS_RESPONSE" | jq -r '.status')
    
    echo "Current job status: $CURRENT_STATUS"
    
    if [ "$CURRENT_STATUS" == "completed" ]; then
        echo ""
        echo "Final job response:"
        echo "$JOB_STATUS_RESPONSE" | jq .
        echo ""
        echo "--- Step 5: Verifying final job status ---"
        echo "SUCCESS: Workflow execution completed successfully!"
        exit 0
elif [ "$CURRENT_STATUS" == "failed" ]; then
        echo ""
        echo "Final job response:"
        echo "$JOB_STATUS_RESPONSE" | jq .
        echo ""
        echo "--- Step 5: Verifying final job status ---"
        echo "ERROR: Workflow execution failed."
        exit 1
fi
    
sleep 10
done

echo "Error: Workflow polling timed out after $MAX_ATTEMPTS attempts."
exit 1