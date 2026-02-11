import { NextRequest, NextResponse } from 'next/server';

const MACHINE_SIMULATOR_URL = process.env.MACHINE_SIMULATOR_URL || 'http://YOUR_MACHINE_SIMULATOR_HOST:YOUR_API_PORT_3';

/**
 * Proxy SSE stream from backend
 */
async function proxyStreamRequest(
  request: NextRequest,
  pathStr: string
): Promise<Response> {
  const url = `${MACHINE_SIMULATOR_URL}/api/machines/${pathStr}`;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return new Response(JSON.stringify({ error }), {
        status: response.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Create a readable stream to pipe SSE data
    const stream = new ReadableStream({
      async start(controller) {
        const reader = response.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            controller.enqueue(value);
          }
        } catch (error) {
          console.error('[SSE Proxy] Stream error:', error);
        } finally {
          controller.close();
          reader.releaseLock();
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    console.error(`[SSE Proxy] Error for ${pathStr}:`, error);
    return new Response(JSON.stringify({ error: 'Failed to connect to stream' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

/**
 * Catch-all proxy for machine-simulator API
 */
async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse | Response> {
  const { path } = await params;
  const pathStr = path.join('/');

  // Handle SSE stream requests specially
  if (pathStr.endsWith('/stream')) {
    return proxyStreamRequest(request, pathStr);
  }

  const url = `${MACHINE_SIMULATOR_URL}/api/machines/${pathStr}`;

  try {
    const options: RequestInit = {
      method: request.method,
      headers: { 'Content-Type': 'application/json' },
    };

    if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
      const body = await request.text();
      if (body) {
        options.body = body;
      }
    }

    const response = await fetch(url, options);

    // Handle non-JSON responses
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    } else {
      const text = await response.text();
      return new NextResponse(text, { status: response.status });
    }
  } catch (error) {
    console.error(`[Machines Proxy] Error for ${pathStr}:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to machine simulator service' },
      { status: 503 }
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export const dynamic = 'force-dynamic';
