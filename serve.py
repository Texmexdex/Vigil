#!/usr/bin/env python3
"""Vigil local server.

Serves the monitor from this folder and relays a short allowlist of public feeds that
refuse to talk to a browser directly. Reachable only from this computer.

    python serve.py          ->  http://127.0.0.1:5599
    python serve.py 8080     ->  another port
"""
import http.server
import json
import os
import threading
import time
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request

ALLOWED = {
    "www2.tceq.texas.gov",      # reported air emission events
    "opendata.adsb.fi",         # aircraft positions
    "api.adsb.lol",             # aircraft positions (backup)
    "opensky-network.org",      # aircraft positions (backup)
    "api.gdeltproject.org",     # news headline search
    "news.google.com",          # news headline search (backup)
    "www.purdue.edu",           # Purdue police daily crime log
}
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PORT = int(ARGS[0]) if ARGS else 5599
RELAY_ONLY = "--relay-only" in sys.argv  # when exposed through a tunnel: answer /relay and nothing else
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
        if parts.path.rstrip("/") == "/history":
            try:
                since = float(urllib.parse.parse_qs(parts.query).get("since", ["0"])[0])
            except ValueError:
                since = 0
            return self.reply(200, history_json(since).encode(), "application/json")
        if RELAY_ONLY:
            return self.reply(404, b"Not found")
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


# ---------------------------------------------------------------- aircraft recorder
# Records helicopters and military aircraft around a fixed point all day, so the app can show
# what passed while it was closed. Settings live in vigil-config.json beside this file.
CONFIG_PATH = os.path.join(ROOT, "vigil-config.json")
HISTORY_PATH = os.path.join(ROOT, "aircraft-history.json")
CONFIG = {"lat": 29.7604, "lon": -95.3698, "radius_nm": 40, "keep_hours": 48, "poll_seconds": 15}
try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        CONFIG.update(json.load(f))
except FileNotFoundError:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2)

HELI_PREFIX = ("EC", "AS3", "AS5", "AS6", "B06", "B40", "B41", "B42", "B43", "B21", "B50", "B52", "H12", "H13",
               "H14", "H15", "H16", "H17", "H47", "H53", "H60", "H64", "H72", "R22", "R44", "R66", "S76", "S92",
               "A109", "A119", "A139", "A169", "A189", "MD5", "MD6", "MD9", "BK17", "UH1", "AH1", "EN28", "EN48", "V22")
LOCK = threading.Lock()
TRACKS = {}  # hex -> {"meta": {...}, "pts": [[t, lat, lon, alt, gs, track], ...]}


def _interesting(a):
    t = (a.get("t") or "").upper()
    heli = a.get("category") == "A7" or t.startswith(HELI_PREFIX)
    mil = bool(int(a.get("dbFlags") or 0) & 1)
    emerg = (a.get("emergency") or "none") != "none" or a.get("squawk") in ("7500", "7600", "7700")
    return heli or mil or emerg, heli, mil, emerg


def _load_history():
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            TRACKS.update(json.load(f))
    except (FileNotFoundError, ValueError):
        pass


def _save_history():
    with LOCK:
        data = json.dumps(TRACKS, separators=(",", ":"))
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, HISTORY_PATH)


def _poll_once():
    url = "https://opendata.adsb.fi/api/v2/lat/%.4f/lon/%.4f/dist/%d" % (CONFIG["lat"], CONFIG["lon"], CONFIG["radius_nm"])
    req = urllib.request.Request(url, headers={"User-Agent": "vigil-recorder (personal aviation log)"})
    with urllib.request.urlopen(req, timeout=20) as res:
        aircraft = json.loads(res.read()).get("aircraft") or []
    now = time.time()
    with LOCK:
        for a in aircraft:
            if a.get("lat") is None or a.get("lon") is None or (a.get("seen_pos") or 0) > 60:
                continue
            keep, heli, mil, emerg = _interesting(a)
            if not keep:
                continue
            hx = a.get("hex")
            tr = TRACKS.setdefault(hx, {"meta": {}, "pts": []})
            meta = tr["meta"]
            for k in ("r", "t", "ownOp", "year", "desc"):
                if a.get(k):
                    meta[k] = a[k]
            if (a.get("flight") or "").strip():
                meta["flight"] = a["flight"].strip()
            meta["heli"], meta["mil"] = heli or meta.get("heli", False), mil or meta.get("mil", False)
            if emerg:
                meta["emerg"] = a.get("squawk") or a.get("emergency")
            alt = a.get("alt_baro") if isinstance(a.get("alt_baro"), (int, float)) else (0 if a.get("alt_baro") == "ground" else None)
            pt = [round(now), round(a["lat"], 5), round(a["lon"], 5), alt, a.get("gs"), a.get("track")]
            pts = tr["pts"]
            # keep a point every 30 s, or sooner when it has turned or moved noticeably
            if not pts or now - pts[-1][0] >= 30 or abs(pts[-1][1] - pt[1]) + abs(pts[-1][2] - pt[2]) > 0.004:
                pts.append(pt)
        cutoff = now - CONFIG["keep_hours"] * 3600
        for hx in list(TRACKS):
            TRACKS[hx]["pts"] = [p for p in TRACKS[hx]["pts"] if p[0] >= cutoff]
            if not TRACKS[hx]["pts"]:
                del TRACKS[hx]


def recorder():
    _load_history()
    last_save = 0
    while True:
        try:
            _poll_once()
        except Exception as err:  # keep recording through network hiccups
            print("recorder:", err, flush=True)
        if time.time() - last_save > 60:
            try:
                _save_history()
                last_save = time.time()
            except OSError as err:
                print("recorder save:", err, flush=True)
        time.sleep(max(5, CONFIG["poll_seconds"]))


def history_json(since):
    with LOCK:
        out = []
        for hx, tr in TRACKS.items():
            pts = [p for p in tr["pts"] if p[0] >= since]
            if pts:
                out.append({"hex": hx, "meta": tr["meta"], "pts": pts})
    return json.dumps({"center": [CONFIG["lat"], CONFIG["lon"]], "radius_nm": CONFIG["radius_nm"], "now": round(time.time()), "aircraft": out}, separators=(",", ":"))


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    if "--no-recorder" not in sys.argv:
        threading.Thread(target=recorder, daemon=True).start()
    print(f"Vigil {'relay' if RELAY_ONLY else 'is'} at http://127.0.0.1:{PORT}{'/relay' if RELAY_ONLY else ''}  (Ctrl+C to stop)")
    Server(("127.0.0.1", PORT), Handler).serve_forever()
