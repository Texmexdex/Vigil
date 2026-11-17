#!/usr/bin/env python3
"""Vigil local server.

Serves the monitor from this folder and relays a short allowlist of public feeds that
refuse to talk to a browser directly. Reachable only from this computer.

    python serve.py          ->  http://127.0.0.1:5599
    python serve.py 8080     ->  another port
"""
import http.server
import os
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request

ALLOWED = {
    "www2.tceq.texas.gov",      # reported air emission events
    "opendata.adsb.fi",         # aircraft positions
    "api.gdeltproject.org",     # news headline search
}
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5599
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        if parts.path.rstrip("/") == "/relay":
            return self.relay(urllib.parse.parse_qs(parts.query).get("u", [""])[0])
        return super().do_GET()

    def reply(self, status, body, ctype="text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def relay(self, target):
        if not target:
            return self.reply(200, b"vigil-relay ok")
        url = urllib.parse.urlsplit(target)
        if url.scheme != "https" or url.hostname not in ALLOWED:
            return self.reply(403, b"Host not allowed")
        req = urllib.request.Request(target, headers={"User-Agent": "vigil-relay (personal emergency monitor)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                return self.reply(res.status, res.read(), res.headers.get("Content-Type", "text/plain"))
        except urllib.error.HTTPError as err:
            return self.reply(err.code, err.read() or b"upstream error")
        except Exception as err:  # network trouble: say so instead of hanging
            return self.reply(502, str(err).encode())


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"Vigil is at http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    Server(("127.0.0.1", PORT), Handler).serve_forever()
