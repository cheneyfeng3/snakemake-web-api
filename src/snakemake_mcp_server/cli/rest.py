import click
import logging
import os
import sys
import uvicorn
import subprocess
import signal
import time
from pathlib import Path
from ..api.main import create_native_fastapi_app

logger = logging.getLogger(__name__)

PID_FILE = Path.home() / ".swa" / "rest.pid"

def get_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, IOError):
            return None
    return None

def is_running(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

@click.group(
    help="Manage the Snakemake REST API server.",
    invoke_without_command=True
)
@click.option("--host", default="127.0.0.1", help="Host to bind to. Default: 127.0.0.1")
@click.option("--port", default=8082, type=int, help="Port to bind to. Default: 8082")
@click.option("--log-level", default="INFO", type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help="Logging level. Default: INFO")
@click.pass_context
def rest(ctx, host, port, log_level):
    """Manage the Snakemake REST API server."""
    ctx.ensure_object(dict)
    ctx.obj['HOST'] = host
    ctx.obj['PORT'] = port
    ctx.obj['LOG_LEVEL'] = log_level

    if ctx.invoked_subcommand is None:
        ctx.invoke(run)

@rest.command(help="Run the server in the foreground (blocking).")
@click.pass_context
def run(ctx):
    """Start the Snakemake server with native FastAPI REST endpoints."""
    host = ctx.obj['HOST']
    port = ctx.obj['PORT']
    log_level = ctx.obj['LOG_LEVEL']

    # Reconfigure logging to respect the user's choice
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    wrappers_path = ctx.obj['WRAPPERS_PATH']
    workflows_dir = ctx.obj['WORKFLOWS_DIR']
    
    logger.info(f"Starting Snakemake Server with native FastAPI REST API...")
    logger.info(f"FastAPI server will be available at http://{host}:{port}")
    logger.info(f"OpenAPI documentation available at http://{host}:{port}/docs")
    logger.info(f"Using snakebase from: {ctx.obj['SNAKEBASE_DIR']}")
    
    if not os.path.isdir(wrappers_path):
        logger.error(f"Wrappers directory not found at: {wrappers_path}")
        sys.exit(1)
    
    if not os.path.isdir(workflows_dir):
        logger.error(f"Workflows directory not found at: {workflows_dir}")
        sys.exit(1)

    app = create_native_fastapi_app(wrappers_path, workflows_dir)
    uvicorn.run(app, host=host, port=port, log_level=log_level.lower())

@rest.command(help="Start the server in the background.")
@click.pass_context
def start(ctx):
    pid = get_pid()
    if is_running(pid):
        click.echo(f"Server is already running (PID: {pid}).")
        return

    host = ctx.obj['HOST']
    port = ctx.obj['PORT']
    log_level = ctx.obj['LOG_LEVEL']
    
    # Ensure log directory exists
    log_dir = Path.home() / ".swa" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log = log_dir / "server.log"

    click.echo(f"Starting Snakemake Server in background on {host}:{port}...")
    
    # Build command to run the 'run' subcommand
    cmd = [
        sys.executable, "-m", "snakemake_mcp_server.server", "rest",
        "--host", host,
        "--port", str(port),
        "--log-level", log_level,
        "run"
    ]
    
    with open(server_log, "a") as f:
        process = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=f,
            preexec_fn=os.setpgrp if os.name != 'nt' else None
        )
    
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(process.pid))
    
    # Give it a second to start and check
    time.sleep(2)
    if is_running(process.pid):
        click.echo(f"Server started (PID: {process.pid}).")
        click.echo(f"Logs: {server_log}")
    else:
        click.echo("Server failed to start. Check logs.")

@rest.command(help="Stop the background server.")
def stop():
    pid = get_pid()
    if not is_running(pid):
        click.echo("Server is not running.")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return

    click.echo(f"Stopping server (PID: {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait a bit for it to stop
        for _ in range(5):
            if not is_running(pid):
                break
            time.sleep(1)
        
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)
            
        click.echo("Server stopped.")
    except OSError as e:
        click.echo(f"Error stopping server: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()

@rest.command(help="Check the status of the server.")
def status():
    pid = get_pid()
    if is_running(pid):
        click.echo(f"Server is running (PID: {pid}).")
        # Try to verify if it's responding?
    else:
        click.echo("Server is not running.")
