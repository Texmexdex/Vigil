# Vigil

A live map of what is being reported near you: fire, EMS and police dispatch, weather alerts,
industrial emission reports, satellite heat detections, air quality, flooding, traffic, low
helicopters, and roadside camera stills. Every item names its publisher and links to it.

## Run it on this computer

    python serve.py

Then open http://127.0.0.1:5599. `serve.py` serves the page and relays the few feeds that refuse
browsers (TCEQ emission reports, aircraft positions, news search). It listens on this computer only.

Opening `index.html` directly also works, but the relay-only feeds stay off.

## Put it on your phone (Cloudflare Pages + GitHub)

1. Create a GitHub repository and add `index.html` and the `functions` folder (with `relay.js` in it).
2. In Cloudflare: Workers & Pages > Create > Pages > Connect to Git, pick the repository.
   No build command; output directory `/`.
3. Open the `*.pages.dev` address on your phone, allow location, and add it to the home screen.

The page finds the relay at `/relay` by itself. Nothing needs to be pasted into settings.

`relay-worker.js` is the same relay as a standalone Worker, only needed if the page is hosted
somewhere other than Cloudflare Pages.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The whole app |
| `serve.py` | Local server with the relay built in |
| `functions/relay.js` | The relay for Cloudflare Pages |
| `relay-worker.js` | The relay as a standalone Cloudflare Worker |

## What needs the relay

TCEQ emission events, helicopters and emergency squawks, and news headlines. Everything else is
read straight from the publisher by your browser.
