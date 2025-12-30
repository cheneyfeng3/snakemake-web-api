# Troubleshooting & Debugging Guide

This document provides solutions for common issues encountered when running the Snakemake Web API, especially in distributed environments like Kubernetes and S3.

## Kubernetes Execution Issues

### 1. `ApiException (404) Not Found` for pods/log
This error occurs when Snakemake tries to fetch logs for a Pod that has already failed and been cleaned up by Kubernetes.

*   **Debug Tip**: Add `kubernetes-omit-job-cleanup: true` to your Snakemake profile. This prevents Snakemake from deleting the failed Jobs/Pods, allowing you to run `kubectl logs` and `kubectl describe` manually to see the error.
*   **Root Cause**: Often caused by the `pip install` step failing or timing out inside the Pod during initialization (e.g., due to slow network or PyPI access issues).
*   **Solution**: Use a **custom container image** with all required storage plugins (`snakemake-storage-plugin-s3`, `snakemake-storage-plugin-http`) pre-installed.
    ```dockerfile
    FROM snakemake/snakemake:v9.11.2
    RUN pip install snakemake-storage-plugin-s3 snakemake-storage-plugin-http
    ```

### 2. Resource Allocation Issues (Pending/Evicted Pods)
If your Pods stay in "Pending" status or are frequently evicted:
*   **CPU Scalar**: Use `kubernetes-cpu-scalar: 0.95` in your profile. K8s reserves some CPU for system use; if your job requests 100% of a node's CPU, it may never be scheduled.
*   **Default Resources**: Set `default-resources` in your profile to ensure every pod has a minimum memory/CPU request.

### 3. MissingInputException in K8s/S3 Mode
If Pods cannot find input files that exist on the SWA server:
*   **Enable Prefill**: Always start the SWA server with the `--prefill` flag when using remote profiles. This ensures local data is synced to S3 before Pods start.
*   **Path Mapping**: Ensure your `units.tsv` or `config.yaml` uses paths relative to the workflow root. SWA uses these relative paths to map local files to the dynamic S3 job prefix.
*   **S3 Credentials**: Verify that `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_ENDPOINT_URL` are correctly set in the server's environment.

## Snakemake Logic Errors

### 1. `TypeError: expected str, bytes or os.PathLike object, not GithubFile`
This error occurs when using the Kubernetes executor with workflows that contain remote `include` directives (URLs).

*   **Deep Analysis**: In Kubernetes mode, the Snakemake leader process (running on the SWA server) must distribute the workflow's source code to the remote Pods. It does this by creating a source archive (`.tar.xz`). 
    *   Snakemake's source archiver expects all rule definitions to originate from local files. 
    *   If a workflow includes rules from a URL (e.g., `include: "https://raw.githubusercontent.com/..."`), Snakemake represents these as `GithubFile` objects rather than standard file paths.
    *   The archiver incorrectly attempts to calculate a relative path for these objects using `os.path.relpath()`, which triggers the `TypeError`.
*   **Solution**: Use **complete, localized workflow code**. 
    1. Download all `.smk` rule files and place them within the `workflow/rules/` directory.
    2. Replace all URL-based `include:` directives with local relative paths (e.g., `include: "rules/align.smk"`).
    3. Ensure the entire workflow directory is self-contained before submitting via the API.

### 2. Config Schema Validation Errors
If you see `ValidationError: '' is not of type 'object'` for params:
*   **Cause**: Snakemake schemas often require specific parameters to be dictionaries/objects, even if they are empty.
*   **Solution**: Ensure your `config.yaml` provides the correct structure. For example, instead of `star: ""`, use:
    ```yaml
    star:
      index: ""
      align: ""
    ```

## Logging & Inspection

### Real-time Logs
*   **SWA Server Output**: Check `~/.swa/logs/server.log` for API-level issues.
*   **Job Console Output**: Use the `log_url` provided by the API:
    ```bash
    curl http://localhost:8082/workflow-processes/{job_id}/log
    ```
*   **Local Disk Logs**: Inspect `~/.swa/logs/{job_id}.log` directly on the server.

### Kubernetes Inspection
*   **Check Events**: `kubectl get events -n <namespace> --sort-by='.lastTimestamp'`
*   **Describe Job**: `kubectl describe job snakejob-{short_id}`
