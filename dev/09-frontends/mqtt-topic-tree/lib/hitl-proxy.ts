// Server-side HITL API client - runs inside the cluster
// Used by API routes to proxy requests to the HITL API

const HITL_API_BASE = process.env.HITL_API_URL || 'http://YOUR_HITL_API_HOST:YOUR_API_PORT';

export async function proxyToHitlApi(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = `${HITL_API_BASE}${path}`;

  console.log(`[HITL Proxy] ${options.method || 'GET'} ${url}`);

  const response = await fetch(url, {
    ...options,
    cache: 'no-store',  // Disable Next.js caching
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  return response;
}

export { HITL_API_BASE };
