import { NextRequest, NextResponse } from 'next/server';

const CHART_ENGINE_URL = process.env.CHART_ENGINE_URL || 'http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3';

/**
 * Proxy requests to the chart-engine backend service
 */
async function proxyRequest(
  request: NextRequest,
  path: string = ''
): Promise<NextResponse> {
  const url = `${CHART_ENGINE_URL}/api${path}`;

  try {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    const options: RequestInit = {
      method: request.method,
      headers,
    };

    // Include body for POST/PUT/PATCH
    if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
      const body = await request.text();
      if (body) {
        options.body = body;
      }
    }

    const response = await fetch(url, options);
    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[Chart Engine Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to chart engine service' },
      { status: 503 }
    );
  }
}

export async function GET(request: NextRequest) {
  // Extract path from URL for routing
  const pathname = new URL(request.url).pathname;
  const path = pathname.replace('/api/chart-engine', '');
  return proxyRequest(request, path || '/skills');
}

export async function POST(request: NextRequest) {
  return proxyRequest(request, '/chart/generate');
}

export const dynamic = 'force-dynamic';
