import { NextRequest, NextResponse } from 'next/server';

const MACHINE_SIMULATOR_URL = process.env.MACHINE_SIMULATOR_URL || 'http://YOUR_MACHINE_SIMULATOR_HOST:YOUR_API_PORT_3';

/**
 * Proxy requests to the machine-simulator backend service
 */
async function proxyRequest(
  request: NextRequest,
  path: string = ''
): Promise<NextResponse> {
  const url = `${MACHINE_SIMULATOR_URL}/api/machines${path}`;

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
    console.error('[Machines Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to machine simulator service' },
      { status: 503 }
    );
  }
}

export async function GET(request: NextRequest) {
  return proxyRequest(request);
}

export async function POST(request: NextRequest) {
  return proxyRequest(request);
}

export const dynamic = 'force-dynamic';
