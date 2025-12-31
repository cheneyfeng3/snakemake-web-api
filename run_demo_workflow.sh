#!/bin/bash
set -e # Exit on error
unset http_proxy https_proxy # Bypass proxy for localhost connections

# This script executes a Snakemake workflow via the /workflow-processes REST API endpoint
# using a contractor command, polls its status, and verifies successful execution.
# It dynamically fetches the demo case from the /demos/workflows/{workflow_id} endpoint.
#
# Usage: ./run_demo_workflow.sh [workflow_id]
# Example: ./run_demo_workflow.sh rna-seq-star-deseq2

# --- Configuration ---
API_SERVER_URL="http://127.0.0.1:8082"
MAX_ATTEMPTS=600 # 10 minutes timeout for workflow polling (workflows usually take longer)
WORKFLOW_ID=${1:-"StainedGlass"}

# --- Step 1: Fetch demo case from /demos/workflows endpoint ---
echo "--- Step 1: Fetching demo case for $WORKFLOW_ID ---"
DEMO_RESPONSE=$(curl -s "$API_SERVER_URL/demos/workflows/$WORKFLOW_ID")

if [ $? -ne 0 ]; then
    echo "Error: Failed to connect to API server at $API_SERVER_URL. Is it running?"
    exit 1
fi

# Check if response is an array and has at least one element
if [ "$(echo "$DEMO_RESPONSE" | jq -r 'type')" != "array" ] || [ "$(echo "$DEMO_RESPONSE" | jq 'length')" -eq 0 ]; then
    echo "Error: No demos found for workflow $WORKFLOW_ID or unexpected API response."
    echo "$DEMO_RESPONSE" | jq .
    exit 1
fi

# Pick the first demo from the list
DEMO_CASE=$(echo "$DEMO_RESPONSE" | jq '.[0]')
DEMO_CONFIG=$(echo "$DEMO_CASE" | jq '.config')

# Construct the payload for /workflow-processes
# UserWorkflowRequest: { workflow_id, config, target_rule }
DEMO_CASE_PAYLOAD=$(jq -n \
                  --arg wid "$WORKFLOW_ID" \
                  --argjson cfg "$DEMO_CONFIG" \
                  '{workflow_id: $wid, config: $cfg}')

echo "Fetched Demo Config Name: $(echo "$DEMO_CASE" | jq -r '.name')"
echo "Payload to be submitted:"
echo "$DEMO_CASE_PAYLOAD" | jq .
echo ""

# --- Step 2: Submit the job ---
echo "--- Step 2: Submitting the workflow job to /workflow-processes ---"

CURL_OUTPUT=$( \
    echo "$DEMO_CASE_PAYLOAD" | \
    curl -s -X POST \
         -H "Content-Type: application/json" \
         -d @- \
         "$API_SERVER_URL/workflow-processes" \
)

echo "Response from /workflow-processes (Job Submission):"
echo "$CURL_OUTPUT" | jq .
echo ""

# --- Step 3: Extract job_id, status_url and log_url from the response ---
echo "--- Step 3: Extracting job_id, status_url and log_url ---"
JOB_ID=$(echo "$CURL_OUTPUT" | jq -r '.job_id')
STATUS_URL_RELATIVE=$(echo "$CURL_OUTPUT" | jq -r '.status_url')
LOG_URL_RELATIVE=$(echo "$CURL_OUTPUT" | jq -r '.log_url')
STATUS_URL="$API_SERVER_URL$STATUS_URL_RELATIVE"
LOG_URL="$API_SERVER_URL$LOG_URL_RELATIVE"

if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
    echo "Error: Failed to get JOB_ID from response."
    echo "Full response: $CURL_OUTPUT"
    exit 1
fi

echo "Job ID: $JOB_ID"
echo "Status URL: $STATUS_URL"
echo "Log URL: $LOG_URL"
echo ""

# --- Step 4: Poll the status_url to monitor job progress ---
echo "--- Step 4: Polling job status ---"
JOB_STATUS=""
ATTEMPT=0

while [ "$JOB_STATUS" != "completed" ] && [ "$JOB_STATUS" != "failed" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    echo "Polling job status... Attempt $((ATTEMPT+1)) of $MAX_ATTEMPTS"
    echo "You can view real-time logs at: $LOG_URL"
    sleep 5 # Poll every 5 seconds for workflows
    JOB_RESPONSE=$(curl -s "$STATUS_URL")
    JOB_STATUS=$(echo "$JOB_RESPONSE" | jq -r '.status')
    echo "Current job status: $JOB_STATUS"
    ATTEMPT=$((ATTEMPT+1))
done

echo ""
echo "Final job response:"
echo "$JOB_RESPONSE" | jq .
echo ""

# --- Step 5: Verify the final job status ---
echo "--- Step 5: Verifying final job status ---"
if [ "$JOB_STATUS" == "completed" ]; then
    echo "SUCCESS: Workflow execution completed successfully!"
    exit 0
else
    echo "ERROR: Workflow execution failed or timed out."
    exit 1
fi
