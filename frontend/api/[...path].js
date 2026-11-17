// Same-origin proxy for the hosted console.
// The browser calls /api, /processor, and /simulator on the Vercel domain.
// This function adds X-API-KEY for /api and streams the upstream body, so the
// key never appears in the Vite bundle. Hobby functions stop at 300 seconds.
// The console already reconnects EventSource on error, which covers that cap.

export const maxDuration = 300

const HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'content-encoding',
  'content-length',
])

function upstreamPath(pathname) {
  if (pathname.startsWith('/api/upstream/')) {
    return pathname.slice('/api/upstream'.length)
  }
  return pathname
}

function allowed(pathname) {
  return pathname === '/api'
    || pathname.startsWith('/api/')
    || pathname.startsWith('/processor/')
    || pathname.startsWith('/simulator/')
}

export async function GET(request) {
  return proxy(request)
}

export async function HEAD(request) {
  return proxy(request)
}

async function proxy(request) {
  const backend = (process.env.HF_BACKEND_URL || '').replace(/\/$/, '')
  if (!backend) {
    return Response.json({ error: 'HF_BACKEND_URL is not set' }, { status: 500 })
  }
  const incoming = new URL(request.url)
  const pathname = upstreamPath(incoming.pathname)
  if (!allowed(pathname) || pathname.includes('..')) {
    return Response.json({ error: 'path not proxied' }, { status: 400 })
  }
  const headers = { accept: request.headers.get('accept') || '*/*' }
  if (pathname === '/api' || pathname.startsWith('/api/')) {
    const apiKey = process.env.SERVICE_API_KEY || ''
    if (!apiKey) {
      return Response.json({ error: 'SERVICE_API_KEY is not set' }, { status: 500 })
    }
    headers['X-API-KEY'] = apiKey
  }
  const target = backend + pathname + incoming.search
  let upstream
  try {
    upstream = await fetch(target, { method: request.method, headers })
  } catch (error) {
    return Response.json({ error: 'backend unreachable', detail: String(error) }, { status: 502 })
  }
  const responseHeaders = new Headers()
  upstream.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) {
      responseHeaders.set(key, value)
    }
  })
  if (pathname.endsWith('/stream') || (upstream.headers.get('content-type') || '').includes('text/event-stream')) {
    responseHeaders.set('cache-control', 'no-cache, no-transform')
    responseHeaders.set('x-accel-buffering', 'no')
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders })
}
