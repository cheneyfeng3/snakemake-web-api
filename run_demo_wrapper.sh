#!/bin/bash
set -x # Enable shell debugging
unset http_proxy https_proxy # Bypass proxy for localhost connections

# This script executes the samtools/faidx wrapper via the /tool-processes REST API endpoint
# using a curl command, polls its status, and verifies successful execution.
# It dynamically fetches the demo case from the /demo-case endpoint.
#
# Prerequisites:
# 1. FastAPI server running on http://127.0.0.1:8082 (e.g., by running 'swa rest --port 8082' in a separate terminal).
# 2. 'jq' command-line JSON processor installed.
# 3. 'curl' installed.

# --- Configuration ---
API_SERVER_URL="http://127.0.0.1:8082"
MAX_ATTEMPTS=60 # 60 seconds timeout for job polling

# --- Step 1: Fetch demo case from /demo-case endpoint ---
echo "--- Step 1: Fetching demo case from /demo-case endpoint ---"
DEMO_CASE_RESPONSE=$(curl -s "$API_SERVER_URL/demo-case")

if [ $? -ne 0 ]; then
    echo "Error: Failed to connect to API server at $API_SERVER_URL. Is it running?"
    exit 1
fi

DEMO_CASE_METHOD=$(echo "$DEMO_CASE_RESPONSE" | jq -r '.method')
DEMO_CASE_ENDPOINT=$(echo "$DEMO_CASE_RESPONSE" | jq -r '.endpoint')
CURL_EXAMPLE=$(echo "$DEMO_CASE_RESPONSE" | jq -r '.curl_example')

if [ "$DEMO_CASE_METHOD" != "POST" ] || [ "$DEMO_CASE_ENDPOINT" != "/tool-processes" ]; then
    echo "Error: Unexpected demo case method or endpoint."
    echo "$DEMO_CASE_RESPONSE" | jq .
    exit 1
fi

echo "Fetched Demo Case:"
echo "$DEMO_CASE_RESPONSE" | jq .
echo ""

# --- Step 2: Execute the curl example from /demo-case to submit the job ---
echo "--- Step 2: Executing the curl example from /demo-case to submit the job ---"
# Extract the payload directly from the DEMO_CASE_RESPONSE
DEMO_CASE_PAYLOAD=$(echo "$DEMO_CASE_RESPONSE" | jq -c '.payload')

# Get the wrapper ID from the payload (FIX: changed from wrapper_name to wrapper_id)
WRAPPER_ID=$(echo "$DEMO_CASE_PAYLOAD" | jq -r '.wrapper_id')

# Construct absolute paths for inputs
SNAKEBASE_DIR=${SNAKEBASE_DIR:-$HOME/snakebase}
DEMO_WORKDIR="$SNAKEBASE_DIR/snakemake-wrappers/$WRAPPER_ID/test" # FIX: changed from WRAPPER_NAME to WRAPPER_ID

# Update the inputs in the payload to be absolute paths
# This handles both list and dictionary inputs
UPDATED_PAYLOAD=$(echo "$DEMO_CASE_PAYLOAD" | jq --arg demo_workdir "$DEMO_WORKDIR" '
    if .inputs | type == "array" then
        .inputs |= map($demo_workdir + "/" + .)
    elif .inputs | type == "object" then
        .inputs |= with_entries(.value = $demo_workdir + "/" + .value)
    else
        .
    end
')

# Construct and execute the curl command safely, piping the payload to avoid quoting issues.
CURL_OUTPUT=$( \
    echo "$UPDATED_PAYLOAD" | \
    curl -X POST \
         -H "Content-Type: application/json" \
         -d @- \
         "$API_SERVER_URL$DEMO_CASE_ENDPOINT" \
)

echo "Response from /tool-processes (Job Submission):"
echo "$CURL_OUTPUT" | jq .
echo ""

# --- Step 3: Extract job_id and status_url from the response ---
echo "--- Step 3: Extracting job_id and status_url ---"
JOB_ID=$(echo "$CURL_OUTPUT" | jq -r '.job_id')
STATUS_URL_RELATIVE=$(echo "$CURL_OUTPUT" | jq -r '.status_url')
STATUS_URL="$API_SERVER_URL$STATUS_URL_RELATIVE"

if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
    echo "Error: Failed to get JOB_ID from response."
    echo "Full response: $CURL_OUTPUT"
    exit 1
fi

echo "Job ID: $JOB_ID"
echo "Status URL: $STATUS_URL"
echo ""

# --- Step 4: Poll the status_url to monitor job progress ---
echo "--- Step 4: Polling job status ---"
JOB_STATUS=""
ATTEMPT=0

while [ "$JOB_STATUS" != "completed" ] && [ "$JOB_STATUS" != "failed" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    echo "Polling job status... Attempt $((ATTEMPT+1)) of $MAX_ATTEMPTS"
    sleep 1
    JOB_RESPONSE=$(curl -s "$STATUS_URL")
    JOB_STATUS=$(echo "$JOB_RESPONSE" | jq -r '.status')
    echo "Current job status: "$JOB_STATUS""
    ATTEMPT=$((ATTEMPT+1))
done

echo ""
echo "Final job response:"
echo "$JOB_RESPONSE" | jq .
echo ""

# --- Step 5: Verify the final job status ---
echo "--- Step 5: Verifying final job status ---"
if [ "$JOB_STATUS" == "completed" ]; then
    echo "SUCCESS: Wrapper execution completed successfully!"
    # The /demo-case endpoint creates the workdir and input file, and the FastAPI server
    # handles the execution and output file creation. This script only verifies the job status.
    exit 0
else
    echo "ERROR: Wrapper execution failed or timed out."
    echo "Job details:"
    echo "$JOB_RESPONSE" | jq '.'
    exit 1
fi