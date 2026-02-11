// Reverse proxy for EMQX dashboard with automatic authentication
// This proxies all requests to EMQX and handles auth transparently

const EMQX_CONFIG = {
  uncurated: {
    url: process.env.EMQX_UNCURATED_API_URL || 'http://YOUR_MQTT_UNCURATED_HOST:YOUR_EMQX_DASHBOARD_PORT',
    username: 'admin',
    password: 'Fl3xT3ch1!',
  },
  curated: {
    url: process.env.EMQX_CURATED_API_URL || 'http://YOUR_MQTT_CURATED_HOST:YOUR_EMQX_DASHBOARD_PORT',
    username: 'admin',
    password: 'Fl3xT3ch1!',
  },
};

// Cache tokens per broker
const tokenCache: Record<string, { token: string; expires: number }> = {};

async function getToken(broker: 'curated' | 'uncurated'): Promise<string> {
  const cached = tokenCache[broker];
  if (cached && cached.expires > Date.now()) {
    return cached.token;
  }

  const config = EMQX_CONFIG[broker];
  const response = await fetch(`${config.url}/api/v5/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: config.username,
      password: config.password,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to authenticate with EMQX');
  }

  const data = await response.json();
  // Cache for 1 hour (EMQX tokens typically last longer)
  tokenCache[broker] = {
    token: data.token,
    expires: Date.now() + 3600000,
  };

  return data.token;
}

export async function GET(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'GET');
}

export async function POST(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'POST');
}

export async function PUT(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'PUT');
}

export async function DELETE(
  request: Request,
  { params }: { params: { path: string[] } }
) {
  return proxyRequest(request, params.path, 'DELETE');
}

async function proxyRequest(
  request: Request,
  pathParts: string[],
  method: string
): Promise<Response> {
  const url = new URL(request.url);
  const broker = (url.searchParams.get('broker') || 'uncurated') as 'curated' | 'uncurated';
  const config = EMQX_CONFIG[broker];

  const path = '/' + pathParts.join('/');
  const targetUrl = `${config.url}${path}${url.search}`;

  try {
    // Get auth token
    const token = await getToken(broker);

    // Build headers
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${token}`,
    };

    // Copy relevant headers from original request
    const contentType = request.headers.get('content-type');
    if (contentType) {
      headers['Content-Type'] = contentType;
    }

    // Make proxied request
    const proxyResponse = await fetch(targetUrl, {
      method,
      headers,
      body: method !== 'GET' ? await request.text() : undefined,
    });

    // Return response with CORS headers
    const responseHeaders = new Headers();
    proxyResponse.headers.forEach((value, key) => {
      if (!['transfer-encoding', 'connection'].includes(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    });

    return new Response(proxyResponse.body, {
      status: proxyResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('[EMQX Proxy] Error:', error);
    return Response.json(
      { error: 'Proxy error' },
      { status: 502 }
    );
  }
}
