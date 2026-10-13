#!/usr/bin/env python3
"""Install RUNLU Private Portfolio sync as a per-user macOS LaunchAgent."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "csu-bot-v2-experimental"
LABEL = "com.runlu.private-portfolio-sync"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
PRIVATE_DIR = ROOT / ".csu-private"
ENV_FILE = PRIVATE_DIR / "private-portfolio.env"
LOG_FILE = PRIVATE_DIR / "private-portfolio-sync.log"
ERR_FILE = PRIVATE_DIR / "private-portfolio-sync.err.log"
PROGRAM = ROOT / "bridge" / "private_portfolio_sync.py"


def run(args, check=True):
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and result.returncode != 0:
        print(result.stdout)
        raise SystemExit(result.returncode)
    return result


def require_ready():
    if sys.platform != "darwin":
        raise SystemExit("This installer is for macOS only.")
    branch = run(["git", "branch", "--show-current"]).stdout.strip()
    if branch != EXPECTED_BRANCH:
        raise SystemExit(
            f"Refusing to install from {branch!r}; switch to {EXPECTED_BRANCH!r} first."
        )
    if not ENV_FILE.exists():
        raise SystemExit(
            "Private Portfolio is not bootstrapped yet. Run:\n"
            "python3 scripts/bootstrap-private-portfolio.py"
        )
    if not PROGRAM.exists():
        raise SystemExit("Private Portfolio sync program is missing.")


def env_from_file():
    allowed = {
        "RUNLU_PRIVATE_PORTFOLIO_URL",
        "RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST",
        "PRIVATE_SNAPSHOT_UPLOAD_TOKEN",
    }
    out = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.split("=", 1)
        key = key.strip()
        if key in allowed:
            out[key] = raw.strip()
    if set(out) != allowed:
        raise SystemExit("Private uploader env file is incomplete.")
    return out


def build_plist():
    env = env_from_file()
    return {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(PROGRAM),
        ],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            **env,
            "RUNLU_PRIVATE_PORTFOLIO_POLL_SECONDS": "180",
            "PYTHONUNBUFFERED": "1",
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(ERR_FILE),
        "ProcessType": "Background",
    }


def install():
    require_ready()
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    with PLIST.open("wb") as handle:
        plistlib.dump(build_plist(), handle, sort_keys=True)
    os.chmod(PLIST, 0o600)

    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, str(PLIST)], check=False)
    run(["launchctl", "bootstrap", domain, str(PLIST)])
    run(["launchctl", "enable", f"{domain}/{LABEL}"])
    run(["launchctl", "kickstart", "-k", f"{domain}/{LABEL}"])

    print("RUNLU Private Portfolio sync installed.")
    print(f"LaunchAgent: {PLIST}")
    print(f"Log: {LOG_FILE}")
    print("Broker submission: DISABLED")


def uninstall():
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", domain, str(PLIST)], check=False)
    try:
        PLIST.unlink()
    except FileNotFoundError:
        pass
    print("RUNLU Private Portfolio sync LaunchAgent removed.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        uninstall()
    else:
        install()
