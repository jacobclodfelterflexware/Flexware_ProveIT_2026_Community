import { NextRequest } from 'next/server';
import http from 'http';

const CHART_ENGINE_HOST = process.env.CHART_ENGINE_HOST || 'YOUR_K8S_SERVICE_HOST';
const CHART_ENGINE_PORT = parseInt(process.env.CHART_ENGINE_PORT || '8000');

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ chartId: string }> }
) {
  const { chartId } = await params;

  console.log(`[Chart Stream Proxy] Connecting to ${CHART_ENGINE_HOST}:${CHART_ENGINE_PORT}/api/chart/stream/${chartId}`);

  // Use a ReadableStream to handle the SSE proxy
  const stream = new ReadableStream({
    start(controller) {
      const req = http.request({
        hostname: CHART_ENGINE_HOST,
        port: CHART_ENGINE_PORT,
        path: `/api/chart/stream/${chartId}`,
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
        },
      }, (res) => {
        console.log(`[Chart Stream Proxy] Response status: ${res.statusCode}`);

        if (res.statusCode !== 200) {
          const error = `event: error\ndata: ${JSON.stringify({ type: 'error', error: `HTTP ${res.statusCode}` })}\n\n`;
          controller.enqueue(new TextEncoder().encode(error));
          controller.close();
          return;
        }

        res.on('data', (chunk: Buffer) => {
          controller.enqueue(chunk);
        });

        res.on('end', () => {
          console.log('[Chart Stream Proxy] Stream ended');
          controller.close();
        });

        res.on('error', (err) => {
          console.error('[Chart Stream Proxy] Response error:', err);
          controller.error(err);
        });
      });

      req.on('error', (err) => {
        console.error('[Chart Stream Proxy] Request error:', err);
        const error = `event: error\ndata: ${JSON.stringify({ type: 'error', error: 'Connection failed' })}\n\n`;
        controller.enqueue(new TextEncoder().encode(error));
        controller.close();
      });

      // Handle client disconnect
      request.signal.addEventListener('abort', () => {
        console.log('[Chart Stream Proxy] Client disconnected');
        req.destroy();
      });

      req.end();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}

export const dynamic = 'force-dynamic';
