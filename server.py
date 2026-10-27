#!/usr/bin/env python3
"""Run: python server.py --host 127.0.0.1 --port 8882."""
import argparse
import hashlib
import json
import os
import re
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from core import Problem, Rehearsal, Store

ROOT = Path(__file__).resolve().parent
COOKIE = "akashic_session"
MAX_BODY = 65536


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, service, public_origin=""):
        super().__init__(address, Handler)
        self.service = service
        self.public_origin = public_origin.rstrip("/")
        self.allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if self.public_origin:
            parsed = urlsplit(self.public_origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path:
                raise ValueError("PUBLIC_ORIGIN must be an http(s) origin with no path")
            self.allowed_hosts.add(parsed.hostname)


class Handler(BaseHTTPRequestHandler):
    server_version = "AkashicRehearsal/1.0"
    sys_version = ""

    def log_message(self, *_):
        # Do not log cookies, prompts, query parameters or provider responses.
        return

    def session(self):
        raw = self.headers.get("Cookie", "")
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
            sid = cookie[COOKIE].value if COOKIE in cookie else ""
        except Exception:
            sid = ""
        self.new_session = not re.fullmatch(r"[a-f0-9]{64}", sid)
        if self.new_session:
            sid = secrets.token_hex(32)
        self.sid = sid
        self.owner = hashlib.sha256(sid.encode()).hexdigest()

    def route(self):
        path = urlsplit(self.path).path
        if path == "/akashic":
            return "/"
        if path.startswith("/akashic/"):
            path = path[len("/akashic"):]
        return path

    def check_host(self):
        host = self.headers.get("Host", "")
        try:
            if urlsplit("http://" + host).hostname not in self.server.allowed_hosts:
                raise Problem("Host is not configured for this app", 421)
        except ValueError:
            raise Problem("Invalid Host header", 400) from None

    def send(self, status, payload, content_type="application/json; charset=utf-8"):
        if not isinstance(payload, bytes):
            payload = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        if getattr(self, "new_session", False):
            value = f"{COOKIE}={self.sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800"
            if self.server.public_origin.startswith("https://"):
                value += "; Secure"
            self.send_header("Set-Cookie", value)
        self.end_headers()
        self.wfile.write(payload)

    def execute(self, callback):
        try:
            self.session()
            self.check_host()
            callback()
        except Problem as exc:
            self.send(exc.status, {"error": str(exc), "details": exc.details})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            self.send(500, {"error": "The request failed. No provider response or credentials were exposed."})

    def do_GET(self):
        self.execute(self.get)

    def get(self):
        path = self.route()
        if path == "/health":
            return self.send(200, {"ok": True, "app": "Akashic Rehearsal", "live_configured": self.server.service.provider.ready,
                                   "local_configured": self.server.service.local_provider.ready,
                                   "provider": "Nebius TokenFactory", "storage": "sqlite", "version": "1.0.0"})
        if path == "/api/state":
            state = self.server.service.state(self.owner)
            state["runtime"] = {"live_configured": self.server.service.provider.ready,
                                "local_configured": self.server.service.local_provider.ready,
                                "local_model": self.server.service.local_provider.model if self.server.service.local_provider.ready else None,
                                "model": self.server.service.provider.model if self.server.service.provider.ready else None}
            return self.send(200, state)
        if path == "/api/export":
            return self.send(200, {"app": "Akashic Rehearsal", "synthetic_public_samples": True,
                                   "workspace": self.server.service.state(self.owner)})
        static = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/index.html": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/styles.css": ("styles.css", "text/css; charset=utf-8")}
        if path in static:
            filename, content_type = static[path]
            return self.send(200, (ROOT / "static" / filename).read_bytes(), content_type)
        raise Problem("Not found", 404)

    def do_POST(self):
        self.execute(self.post)

    def body(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise Problem("Mutations require application/json", 415)
        origin = self.headers.get("Origin", "")
        allowed = {"http://" + self.headers.get("Host", ""), "https://" + self.headers.get("Host", "")}
        if self.server.public_origin:
            allowed.add(self.server.public_origin)
        if origin not in allowed:
            raise Problem("A matching Origin is required for workspace changes", 403)
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise Problem("A valid Content-Length is required", 411) from None
        if length <= 0 or length > MAX_BODY:
            raise Problem("JSON body must be between 1 and 65536 bytes", 413)
        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise Problem("Malformed JSON", 400) from None
        if not isinstance(data, dict):
            raise Problem("JSON body must be an object", 400)
        return data

    def post(self):
        data, path, service = self.body(), self.route(), self.server.service
        if path == "/api/candidates":
            return self.send(201, service.candidate(self.owner, data))
        match = re.fullmatch(r"/api/candidates/([a-f0-9]{32})/(preview|adopt)", path)
        if match:
            candidate_id, action = match.groups()
            result = service.preview(self.owner, candidate_id, data) if action == "preview" else service.adopt(self.owner, candidate_id, data)
            return self.send(200, result)
        match = re.fullmatch(r"/api/policies/([a-f0-9]{32})/retire", path)
        if match:
            return self.send(200, service.retire(self.owner, match[1], data))
        match = re.fullmatch(r"/api/tasks/([a-z-]+)/run", path)
        if match:
            return self.send(200, service.run(self.owner, match[1], data))
        if path == "/api/evaluate":
            return self.send(200, service.evaluate(self.owner, data))
        if path == "/api/reset":
            if data.get("confirm") != "reset my synthetic workspace":
                raise Problem("Explicit reset confirmation required")
            return self.send(200, service.reset(self.owner))
        raise Problem("Not found", 404)


def main():
    parser = argparse.ArgumentParser(description="Akashic Rehearsal — synthetic, scoped correction workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8882)
    parser.add_argument("--db", default=str(ROOT / "data" / "rehearsal.sqlite3"))
    parser.add_argument("--data-dir", default=os.environ.get("DATA_DIR", ""))
    parser.add_argument("--public-origin", default=os.environ.get("PUBLIC_ORIGIN", ""))
    args = parser.parse_args()
    if args.data_dir:
        args.db = str(Path(args.data_dir) / "rehearsal.sqlite3")
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    server = AppServer((args.host, args.port), Rehearsal(Store(args.db)), args.public_origin)
    print(f"Akashic Rehearsal listening on http://{args.host}:{server.server_port}", flush=True)
    print("Live NVIDIA/Nebius configured: " + str(server.service.provider.ready), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
