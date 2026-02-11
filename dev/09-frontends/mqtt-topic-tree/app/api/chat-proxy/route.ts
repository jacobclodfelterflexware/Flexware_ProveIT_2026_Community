// POST /api/chat-proxy
// Proxies chat requests to the machine-simulator backend service
// Handles both streaming and non-streaming responses
import { NextRequest, NextResponse } from 'next/server';

const MACHINE_SIMULATOR_URL = process.env.MACHINE_SIMULATOR_URL || 'http://YOUR_MACHINE_SIMULATOR_HOST:YOUR_API_PORT_3';

export async function POST(request: NextRequest) {
  const url = `${MACHINE_SIMULATOR_URL}/api/chat/completion`;

  try {
    const body = await request.json();
    const isStreaming = body.stream !== false;

    console.log('[Chat Proxy] Request:', {
      machine: body.machine_context?.name,
      stream: isStreaming,
      messageLength: body.user_message?.length,
    });

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Chat Proxy] Backend error:', errorText);
      return NextResponse.json(
        { error: 'Chat service error', details: errorText },
        { status: response.status }
      );
    }

    if (isStreaming) {
      // For streaming responses, pass through the SSE stream
      const readable = response.body;
      if (!readable) {
        return NextResponse.json(
          { error: 'No response body from chat service' },
          { status: 500 }
        );
      }

      // Create a TransformStream to pass through the data
      const { readable: outputReadable, writable } = new TransformStream();
      readable.pipeTo(writable);

      return new NextResponse(outputReadable, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        },
      });
    } else {
      // For non-streaming, just pass through the JSON response
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    }
  } catch (error) {
    console.error('[Chat Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to chat service', details: (error as Error).message },
      { status: 503 }
    );
  }
}

export const dynamic = 'force-dynamic';
