# RUNLU Private Portfolio

RUNLU CSU Bot uses a two-layer phone architecture:

1. **PUBLIC Monitor** — public robot health and research status only.
2. **PRIVATE Portfolio** — authenticated read-only funds and holdings.

The private layer never exposes brokerage credentials or trading controls.

## Data published to the private phone view

Only this minimized snapshot is stored:

- currency;
- cash;
- buying power;
- estimated equity derived from cash + displayed position market values;
- position symbol;
- position quantity;
- position average cost;
- position market value;
- open-order count only;
- snapshot timestamp.

The following are explicitly excluded:

- account IDs;
- SnapTrade/Webull credentials;
- access tokens;
- transaction history;
- order IDs, prices, or order detail;
- approval tokens;
- brokerage write routes.

## Authentication

The private page uses server-side authentication.

- Username is stored as a Worker secret.
- Password is never stored in the page.
- Password verification uses PBKDF2-SHA256 with 210,000 iterations and a random salt.
- Successful login creates an HMAC-signed, HttpOnly, Secure, SameSite=Strict session cookie.
- Session lifetime is 8 hours.
- Five failed logins from the same Cloudflare client IP trigger a 15-minute rate limit.
- Private API responses are no-store and do not enable public CORS.

The private UI cannot approve a trade or place/modify/cancel an order.

## Cloudflare storage requirement

Create a Workers KV namespace and bind it to the Worker with binding name:

PRIVATE_PORTFOLIO

The repository intentionally does not contain a KV namespace ID.

## Required Worker secrets

Configure these only in Cloudflare/Wrangler secrets, never in Git:

- PRIVATE_PORTFOLIO_USERNAME
- PRIVATE_PORTFOLIO_PASSWORD_HASH
- PRIVATE_PORTFOLIO_PASSWORD_SALT
- PRIVATE_SESSION_SECRET
- PRIVATE_SNAPSHOT_UPLOAD_TOKEN

PRIVATE_SNAPSHOT_UPLOAD_TOKEN is a dedicated upload-only secret. It is not
CSU_SNAPSHOT_TOKEN and grants no access to CSU proposal/research endpoints.

## Generate password verifier locally

Generate a random salt and PBKDF2 verifier locally. Example Python:

~~~bash
python3 - <<'PY'
import hashlib, secrets, getpass
password = getpass.getpass("Private Portfolio password: ")
salt = secrets.token_urlsafe(24)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210000).hex()
print("PRIVATE_PORTFOLIO_PASSWORD_SALT=" + salt)
print("PRIVATE_PORTFOLIO_PASSWORD_HASH=" + digest)
print("PRIVATE_SESSION_SECRET=" + secrets.token_urlsafe(48))
print("PRIVATE_SNAPSHOT_UPLOAD_TOKEN=" + secrets.token_urlsafe(48))
PY
~~~

Store the printed values directly as Worker secrets. Do not commit them or paste
them into documentation/issues.

## Private routes

- POST /api/private/login
- POST /api/private/logout
- GET /api/private/session
- GET /api/private/portfolio
- POST /api/private/snapshot — upload-only token required

Private UI:

/private.html

Public phone monitor:

/monitor.html

## Mac upload path

bridge/private_portfolio_upload.py reads the already-sanitized local account
snapshot and performs a second minimization pass before sending anything off the
Mac.

Required Mac-local environment values:

- RUNLU_PRIVATE_PORTFOLIO_URL=https://<exact-worker-host>/api/private/snapshot
- RUNLU_PRIVATE_PORTFOLIO_ALLOWED_HOST=<exact-worker-host>
- PRIVATE_SNAPSHOT_UPLOAD_TOKEN=<dedicated-upload-secret>

The uploader requires HTTPS, rejects userinfo/fragments, requires the exact
allowlisted host and exact /api/private/snapshot path, and validates the
destination before reading the upload token.

The Worker rejects snapshots more than 30 minutes old or more than 5 minutes in
the future.

## Deployment boundary

Code readiness is not runtime readiness.

Until the KV binding and Worker secrets are configured and the V2 Worker is
deployed, /private.html is only an implemented interface and cannot display a
live portfolio.

The public GitHub Pages monitor remains separate and contains no private
portfolio data.
