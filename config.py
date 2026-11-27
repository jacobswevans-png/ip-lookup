import os
from pathlib import Path

RUNNER_API_KEY = os.environ.get("RUNNER_API_KEY", "").strip()
if not RUNNER_API_KEY:
    raise SystemExit("RUNNER_API_KEY must be set before the runner starts")

BOT_ROOT = Path(os.environ.get("BOT_ROOT", "/data/bots")).resolve()
BOT_ROOT.mkdir(parents=True, exist_ok=True)

SANDBOX = os.environ.get("SANDBOX", "auto").strip().lower()
BOT_IMAGE = os.environ.get("BOT_IMAGE", "python:3.12-slim")
BOT_CPUS = os.environ.get("BOT_CPUS", "0.5")
BOT_MEMORY = os.environ.get("BOT_MEMORY", "256m")
BOT_MEMORY_BYTES = int(os.environ.get("BOT_MEMORY_BYTES", str(256 * 1024 * 1024)))
BOT_PIDS = int(os.environ.get("BOT_PIDS", "128"))
MAX_FILES = int(os.environ.get("MAX_FILES", "60"))
MAX_BYTES = int(os.environ.get("MAX_BYTES", str(2 * 1024 * 1024)))
LOG_LINES = int(os.environ.get("LOG_LINES", "1000"))
BOT_USER_ID = int(os.environ.get("BOT_USER_ID", "65534"))


def sandbox_mode():
    if SANDBOX in ("docker", "process"):
        return SANDBOX
    return "docker" if Path("/var/run/docker.sock").exists() else "process"
