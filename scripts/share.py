# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Share the app from this computer with friends: an HTTPS link that works on phones (camera included).

Starts a free Cloudflare quick tunnel (no account needed) and the app in public mode, then prints an invite
link. Your computer has to stay on while friends use it; Ctrl+C stops everything and the link dies with it.

  .venv\\Scripts\\python scripts\\share.py            # needs cloudflared: winget install Cloudflare.cloudflared
  .venv\\Scripts\\python scripts\\share.py --no-user-keys   # friends use only the keys in your .env

What friends get:
- each phone sees only its own profiles, history and shelf (PROFILE_SCOPE=device);
- they can type their own Gemini or OpenAI key in the AI settings (unless --no-user-keys);
- without any key the analysis, Skin Score, routine and a rule-based comment still work.
The invite link contains the access token: send it only to people you trust.
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-user-keys", action="store_true", help="friends cannot enter their own API keys")
    args = parser.parse_args()

    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        raise SystemExit("cloudflared bulunamadı. Kurun ve tekrar deneyin:\n"
                         "  Windows: winget install Cloudflare.cloudflared\n"
                         "  macOS:   brew install cloudflared\n"
                         "  Linux:   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("Önce arayüzü derleyin: cd frontend; npm ci; npm run build")

    tunnel = subprocess.Popen([cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{args.port}"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    url = None
    for line in tunnel.stdout:  # cloudflared prints the random address once the tunnel is up
        match = URL.search(line)
        if match:
            url = match.group(0)
            break
    if not url:
        tunnel.terminate()
        raise SystemExit("Tünel adresi alınamadı; internet bağlantınızı kontrol edin.")
    # Keep draining the tunnel's log so its pipe never fills up.
    threading.Thread(target=lambda: [None for _ in tunnel.stdout], daemon=True).start()

    host = url.removeprefix("https://")
    token = os.getenv("APP_ACCESS_TOKEN") or secrets.token_urlsafe(32)
    env = {
        **os.environ,
        "PUBLIC_DEPLOYMENT": "true",
        "APP_ACCESS_TOKEN": token,
        "ALLOWED_HOSTS": f"{host},localhost,127.0.0.1",
        "CORS_ORIGINS": url,
        "PROFILE_SCOPE": "device",
        "ALLOW_USER_API_KEYS": "false" if args.no_user_keys else "true",
    }
    print("\n  SkinCare Vision AI paylaşılıyor\n")
    print(f"  Davet bağlantısı : {url}/#erisim={token}")
    print(f"  (Adres: {url}  ·  erişim anahtarı: {token})")
    print("\n  Bağlantıyı yalnızca güvendiğiniz kişilere gönderin. Durdurmak için Ctrl+C.\n")
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.server:app", "--app-dir", "src", "--host", "127.0.0.1",
                               "--port", str(args.port), "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"], cwd=ROOT, env=env)
    try:
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (server, tunnel):
            process.terminate()


if __name__ == "__main__":
    main()
