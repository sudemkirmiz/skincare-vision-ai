# Deployment and sharing

The app defaults to a private, single-user install on `127.0.0.1`. This page covers sharing it with friends, running it in Docker and putting it on the internet.

## Share it with friends from your computer

One command creates a free HTTPS link through a Cloudflare quick tunnel. HTTPS matters: phone cameras only work on secure pages.

```powershell
winget install Cloudflare.cloudflared        # macOS: brew install cloudflared
cd frontend; npm ci; npm run build; cd ..    # once
.\.venv\Scripts\python scripts\share.py
```

It prints an invite link such as `https://random-words.trycloudflare.com/#erisim=…`. Opening it saves the access token on that device, so nobody types it; the fragment never reaches any server and is removed from the address bar. The link works while your computer is on and changes on every run. In this mode the script sets:

- `PUBLIC_DEPLOYMENT=true` with a fresh random `APP_ACCESS_TOKEN`, and host and CORS allowlists for the tunnel address;
- `PROFILE_SCOPE=device`: each phone sees only its own profiles, history, journal and shelf;
- `ALLOW_USER_API_KEYS=true`, so friends can bring their own Gemini or OpenAI key (`--no-user-keys` allows only the keys in your `.env`);
- Uvicorn with proxy headers trusted from the tunnel only, so rate limits apply per friend.

Send the link only to people you trust: anyone who has it can use the app.

## Docker

### Local

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs -f app
docker compose down
```

The app is exposed only on <http://127.0.0.1:8000>. The named `skincare-vision-ai-state` volume keeps the SQLite data; `docker compose down --volumes` deletes it on purpose.

### Production overlay

```powershell
Copy-Item .env.production.example .env.production
# Fill in the token, host name, origins and provider keys.

$env:ENV_FILE = ".env.production"
docker compose --env-file .env.production `
  -f compose.yaml `
  -f compose.production.yaml `
  up --build -d
```

The overlay forces `PUBLIC_DEPLOYMENT=true` and `ALLOW_USER_API_KEYS=false`, and Compose fails closed when the token, allowed hosts or CORS origins are empty.

### Container hardening

- Multi-stage Node/Python build and a fixed non-root user `10001:10001`
- Read-only root filesystem; only `/tmp` and `/app/state` are writable
- All Linux capabilities dropped, `no-new-privileges`, PID and log-size limits
- Clean signal handling through `tini` and a readiness-aware `/api/health` check
- One worker, so in-memory rate limits, caches and circuit breakers stay consistent

Tagged `v*` releases and manually dispatched Container workflows publish the image to GHCR with SBOM and provenance attestations.

## Always-on hosting

The image needs about 2 GB of memory for the models. It runs on any container host, for example Google Cloud Run, a small VPS or Oracle Cloud's free virtual machine. Hugging Face Docker Spaces now require a paid plan.

## Production checklist

1. Generate an access token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Set the production values:

   ```dotenv
   PUBLIC_DEPLOYMENT=true
   APP_ACCESS_TOKEN=replace-with-generated-secret
   ALLOWED_HOSTS=skin.example.com
   CORS_ORIGINS=https://skin.example.com
   PROFILE_SCOPE=device
   ALLOW_USER_API_KEYS=false   # true lets visitors bring their own key
   ```

3. Put the app behind a TLS reverse proxy and enforce connection, body-size and rate limits there too.
4. Never publish `.env`, `data/history.db`, user images or backups; define encrypted backups and a retention policy.
5. Rotate provider keys and give them the smallest practical quota.
6. Keep the CI security checks, CodeQL and Dependabot alerts enabled.

`APP_ACCESS_TOKEN` plus device scope suits a group of trusted people. A public multi-user service still needs real accounts (for example OIDC), per-user authorization, central rate limiting and audit logging. See [SECURITY.md](../SECURITY.md) for the built-in protections.
