// POST /api/knowledge-chat
// Proxies knowledge base chat requests to the machine-simulator KB chat endpoint
// Handles both streaming and non-streaming responses
import { NextRequest, NextResponse } from 'next/server';

const MACHINE_SIMULATOR_URL = process.env.MACHINE_SIMULATOR_URL || 'http://YOUR_MACHINE_SIMULATOR_HOST:YOUR_API_PORT_3';

export async function POST(request: NextRequest) {
  const url = `${MACHINE_SIMULATOR_URL}/api/kb-chat/completion`;

  try {
    const body = await request.json();
    const isStreaming = body.stream !== false;

    console.log('[KB Chat Proxy] Request:', {
      stream: isStreaming,
      messageLength: body.user_message?.length,
      hasRagContext: !!body.rag_context,
      hasGraphSummary: !!body.graph_summary,
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
      console.error('[KB Chat Proxy] Backend error:', errorText);
      return NextResponse.json(
        { error: 'KB chat service error', details: errorText },
        { status: response.status }
      );
    }

    if (isStreaming) {
      const readable = response.body;
      if (!readable) {
        return NextResponse.json(
          { error: 'No response body from KB chat service' },
          { status: 500 }
        );
      }

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
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    }
  } catch (error) {
    console.error('[KB Chat Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to KB chat service', details: (error as Error).message },
      { status: 503 }
    );
  }
}

export const dynamic = 'force-dynamic';
