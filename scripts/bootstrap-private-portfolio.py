#!/usr/bin/env python3
"""One-command Cloudflare bootstrap for RUNLU Private Portfolio.

Safety:
- Refuses to run outside csu-bot-v2-experimental.
- Requires an existing Wrangler login.
- Creates a separate private Worker environment.
- Generates secrets locally and uploads them in one bulk request.
- Never prints the password, password hash, session secret, or upload token.
- Saves only the upload token + worker URL in .csu-private/private-portfolio.env
  with chmod 0600 for the Mac uploader.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "wrangler.jsonc"
PRIVATE_DIR = ROOT / ".csu-private"
LOCAL_ENV = PRIVATE_DIR / "private-portfolio.env"
EXPECTED_BRANCH = "csu-bot-v2-experimental"
ENV_NAME = "private"
WORKER_NAME = "runlu-csu-investment-ai-private"
KV_BINDING = "PRIVATE_PORTFOLIO"


def run(args, *, input_text=None, check=True):
    result = subprocess.run(
        args,
        cwd=ROOT,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and result.returncode != 0:
        print(result.stdout)
        raise SystemExit(result.returncode)
    return result


def current_branch():
    result = run(["git", "branch", "--show-current"])
    return result.stdout.strip()


def ensure_branch():
    branch = current_branch()
    if branch != EXPECTED_BRANCH:
        raise SystemExit(
            f"Refusing to bootstrap from branch {branch!r}. "
            f"Switch to {EXPECTED_BRANCH!r} first."
        )


def ensure_wrangler_auth():
    result = run(["npx", "wrangler", "whoami"], check=False)
    if result.returncode != 0:
        print(result.stdout)
        raise SystemExit(
            "Wrangler is not logged in. Run: npx wrangler login\n"
            "Then re-run this bootstrap."
        )


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save_config(config):
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def ensure_private_env():
    config = load_config()
    envs = config.setdefault("env", {})
    private = envs.setdefault(ENV_NAME, {})
    private["name"] = WORKER_NAME
    private["vars"] = {
        "CSU_SYMBOL": "CSU",
        "CSU_EXCHANGE": "TSX",
    }
    bindings = private.setdefault("kv_namespaces", [])
    if not any(item.get("binding") == KV_BINDING for item in bindings if isinstance(item, dict)):
        bindings.append({"binding": KV_BINDING})
    save_config(config)


def provision_private_worker():
    """Deploy once so Wrangler can auto-provision the draft KV binding."""
    ensure_private_env()
    result = run(["npx", "wrangler", "deploy", "--env", ENV_NAME])
    return result.stdout


def prompt_credentials():
    print("\nCreate the PRIVATE Portfolio login.")
    username = input("Username: ").strip()
    if len(username) < 3 or len(username) > 64:
        raise SystemExit("Username must be 3-64 characters.")

    password = getpass.getpass("Password (14+ characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    if len(password) < 14:
        raise SystemExit("Password must be at least 14 characters.")

    salt = secrets.token_urlsafe(24)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 210_000
    ).hex()
    session_secret = secrets.token_urlsafe(48)
    upload_token = secrets.token_urlsafe(48)
    password = ""
    confirm = ""
    return {
        "PRIVATE_PORTFOLIO_USERNAME": username,
        "PRIVATE_PORTFOLIO_PASSWORD_HASH": password_hash,
        "PRIVATE_PORTFOLIO_PASSWORD_SALT": salt,
        "PRIVATE_SESSION_SECRET": session_secret,
        "PRIVATE_SNAPSHOT_UPLOAD_TOKEN": upload_token,
    }


def put_secrets(values):
    payload = json.dumps(values)
    result = run(
        ["npx", "wrangler", "secret", "bulk", "--env", ENV_NAME],
        input_text=payload,
    )
    if "error" in result.stdout.lower() and "success" not in result.stdout.lower():
        print(result.stdout)
        raise SystemExit("Cloudflare secret upload may have failed.")
    return values["PRIVATE_SNAPSHOT_UPLOAD_TOKEN"]


def deploy_worker():
    result = run(["npx", "wrangler", "deploy", "--env", ENV_NAME])
    urls = re.findall(r"https://[A-Za-z0-9._~-]+\.workers\.dev(?:/[^\s]*)?", result.stdout)
    if not urls:
        print(result.stdout)
        raise SystemExit(
            "Worker deployed, but the workers.dev URL could not be detected. "
            "Open Cloudflare Workers & Pages and copy the private worker URL."
        )
    return urls[-1].rstrip("/")


def write_local_uploader_env(worker_url, upload_token):
    parsed = urlparse(worker_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit("Deployed Worker URL is not valid HTTPS.")
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    body = (
        f"RUNLU_PRIVATE_PORTFOLIO_URL={worker_url}/api/private/snapshot\n"
        f"RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST={parsed.hostname}\n"
        f"PRIVATE_SNAPSHOT_UPLOAD_TOKEN={upload_token}\n"
    )
    LOCAL_ENV.write_text(body, encoding="utf-8")
    os.chmod(LOCAL_ENV, stat.S_IRUSR | stat.S_IWUSR)


def main():
    print("RUNLU Private Portfolio bootstrap")
    print("No brokerage write permissions will be created.")
    ensure_branch()
    ensure_wrangler_auth()
    provision_output = provision_private_worker()
    print(f"KV binding ready: {KV_BINDING} (Wrangler auto-provisioned/reused)")
    values = prompt_credentials()
    upload_token = put_secrets(values)
    print("Private authentication secrets uploaded.")
    worker_url = deploy_worker()
    write_local_uploader_env(worker_url, upload_token)
    print("\nPRIVATE Portfolio deployed.")
    print("Phone login:")
    print(f"{worker_url}/private.html")
    print("Public-safe status:")
    print(f"{worker_url}/api/private/status")
    print(f"Mac uploader config saved privately to: {LOCAL_ENV.relative_to(ROOT)}")
    print("Next: run the local read-only bridge, then upload a fresh minimized snapshot.")
    print("Optional auto-start: python3 scripts/install-private-portfolio-sync.py")


if __name__ == "__main__":
    main()
