# Vigil

A live map of what is being reported near you: fire, EMS and police dispatch, weather alerts,
industrial emission reports, satellite heat detections, air quality, flooding, traffic, low
helicopters, roadside camera stills, and unverified chatter. Every item names its publisher and
links to it.

**Live:** https://vigil.texmexdex11.workers.dev (works on a phone; add it to the home screen)

## How it fits together

| Piece | Where it runs | What it does |
| --- | --- | --- |
| `index.html` | Your browser | The whole app. Reads most feeds directly. |
| `worker.js` | Cloudflare Worker `vigil` | Serves the app at `/` and the relay at `/relay` for feeds that refuse browsers (TCEQ, news). |
| `vigil-relay.ps1` + `serve.py` | This PC | Aircraft feeds refuse Cloudflare, so the Worker sends those requests to `serve.py` on this PC through a Cloudflare quick tunnel. |

The PC side starts at sign-in through the Windows scheduled task **Vigil home relay**. Each start
opens a new tunnel and registers its address with the Worker (`POST /register`), using the private
key in `.relay-key`. That key is never committed. If the PC is off, only the helicopter layer stops.

The GitHub Pages copy of `index.html` uses the same Worker relay.

## Updating the Worker

    npx wrangler deploy

`wrangler.toml` holds the Worker name and its KV binding (`VIGIL`, which stores the tunnel address).
The register key is a Worker secret: `npx wrangler secret put REGISTER_KEY`.

`worker.js` contains a copy of `index.html`. After changing the page, rebuild it so the two match
(paste the page into the `PAGE` string at the bottom of `worker.js`), then deploy.

## Running it locally

    python serve.py

Then open http://127.0.0.1:5599. This serves the page with the relay built in.
`python serve.py 5600 --relay-only` answers `/relay` only; that is what the tunnel exposes.

## Logs

- `%TEMP%\vigil-relay.log`: each start of the home relay, and whether it registered
- `%TEMP%\vigil-tunnel.log`: the Cloudflare tunnel

## Other files

| File | What it is |
| --- | --- |
| `functions/relay.js` | The relay as a Cloudflare Pages function (only if you host on Pages instead) |
| `relay-worker.js` | The relay as a standalone Worker (only if you host the page elsewhere) |
