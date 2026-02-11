import { NextRequest, NextResponse } from 'next/server';

const ML_PREDICTOR_URL = process.env.ML_PREDICTOR_URL || 'http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3';

/**
 * Catch-all proxy for ml-predictor API
 */
async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse | Response> {
  const { path } = await params;
  const pathStr = path.join('/');

  // Build full URL with query params
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${ML_PREDICTOR_URL}/api/${pathStr}${searchParams ? `?${searchParams}` : ''}`;

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
    const contentType = response.headers.get('content-type');

    // Handle SSE streaming - pass through directly without buffering
    if (contentType?.includes('text/event-stream')) {
      return new Response(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        },
      });
    }

    // Handle JSON responses
    if (contentType?.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    }

    // Handle other content types
    const text = await response.text();
    return new NextResponse(text, { status: response.status });
  } catch (error) {
    console.error(`[ML Proxy] Error for ${pathStr}:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to ML predictor service' },
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

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context);
}

export const dynamic = 'force-dynamic';
