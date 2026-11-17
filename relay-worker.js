/**
 * Vigil relay as a standalone Cloudflare Worker.
 *
 * Use this only if the page is hosted somewhere other than Cloudflare Pages. Create a Worker,
 * paste this file in, deploy, then put the Worker address into Vigil under Layers > Relay.
 * It fetches a short allowlist of public feeds that refuse to talk to a browser directly.
 */
const ALLOWED = new Set([
  'www2.tceq.texas.gov',   // reported air emission events
  'opendata.adsb.fi',      // aircraft positions
  'api.gdeltproject.org',  // news headline search
]);
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET, OPTIONS' };

async function onRequest({ request }) {
  if (request.method === 'OPTIONS') return new Response(null, { headers: CORS });
  if (request.method !== 'GET') return new Response('GET only', { status: 405, headers: CORS });

  const raw = new URL(request.url).searchParams.get('u');
  if (!raw) return new Response('vigil-relay ok', { headers: CORS });

  let target;
  try { target = new URL(raw); } catch { return new Response('Bad address', { status: 400, headers: CORS }); }
  if (target.protocol !== 'https:' || !ALLOWED.has(target.hostname)) return new Response('Host not allowed', { status: 403, headers: CORS });

  // aircraft positions go stale in seconds; everything else can be held briefly
  const ttl = target.hostname === 'opendata.adsb.fi' ? 20 : 120;
  try {
    const upstream = await fetch(target.toString(), { headers: { 'user-agent': 'vigil-relay (personal emergency monitor)' }, cf: { cacheTtl: ttl, cacheEverything: true } });
    return new Response(upstream.body, { status: upstream.status, headers: { ...CORS, 'content-type': upstream.headers.get('content-type') || 'text/plain', 'cache-control': `public, max-age=${ttl}` } });
  } catch (err) {
    return new Response(String(err), { status: 502, headers: CORS });
  }
}

export default { fetch: request => onRequest({ request }) };
