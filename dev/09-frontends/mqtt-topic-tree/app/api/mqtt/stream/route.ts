import { NextRequest } from 'next/server';
import mqtt from 'mqtt';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  // Get topics from query parameter (comma-separated)
  const topicsParam = request.nextUrl.searchParams.get('topics');
  const topicFilters = topicsParam ? topicsParam.split(',').map(t => t.trim()) : [];

  // Get broker selection - 'curated' or default to uncurated
  const brokerParam = request.nextUrl.searchParams.get('broker');
  const isCurated = brokerParam === 'curated' || topicFilters.some(t => t.includes('curated'));

  // Select broker URL based on parameter or topic content
  // Use TCP (mqtt://) instead of WebSocket (ws://) to avoid ws package bundling issues with Next.js
  const brokerUrl = isCurated
    ? process.env.MQTT_BROKER_URL_CURATED || 'mqtt://YOUR_MQTT_CURATED_HOST:YOUR_MQTT_PORT'
    : process.env.MQTT_BROKER_URL || 'mqtt://YOUR_MQTT_UNCURATED_HOST:YOUR_MQTT_PORT';

  console.log(`[MQTT SSE] Using ${isCurated ? 'CURATED' : 'UNCURATED'} broker (TCP): ${brokerUrl}`);

  const stream = new ReadableStream({
    start(controller) {
      const client = mqtt.connect(
        brokerUrl,
        {
          username: process.env.MQTT_USERNAME || 'YOUR_MQTT_USERNAME',
          password: process.env.MQTT_PASSWORD || 'YOUR_MQTT_PASSWORD',
          clientId: `mqtt-topic-tree-sse-${Date.now()}`,
        }
      );

      client.on('connect', () => {
        console.log('[MQTT SSE] Connected to broker');

        // Subscribe to specific topics or all topics
        const subscribeTopics = topicFilters.length > 0 ? topicFilters : ['#'];
        client.subscribe(subscribeTopics, { qos: 0 }, (err) => {
          if (err) {
            console.error('[MQTT SSE] Subscribe error:', err);
          } else {
            console.log(`[MQTT SSE] Subscribed to: ${subscribeTopics.join(', ')}`);
          }
        });
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'connected', topics: subscribeTopics })}\n\n`));
      });

      client.on('message', (topic, payloadBuffer) => {
        // Log received message for debugging
        console.log(`[MQTT SSE] Received message on topic: ${topic}`);

        // Parse the payload
        let payload: Record<string, unknown> = {};
        try {
          const payloadStr = payloadBuffer.toString();
          const parsed = JSON.parse(payloadStr);
          if (typeof parsed === 'object' && parsed !== null) {
            payload = parsed;
          } else {
            payload = { value: parsed };
          }
        } catch {
          // Not JSON, treat as raw value
          const rawValue = payloadBuffer.toString();
          const numValue = parseFloat(rawValue);
          payload = { value: isNaN(numValue) ? rawValue : numValue };
        }

        const data = { type: 'message', topic, payload, timestamp: Date.now() };
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      });

      client.on('error', (err) => {
        console.error('[MQTT SSE] Error:', err);
      });

      client.on('close', () => {
        console.log('[MQTT SSE] Connection closed');
      });

      // Cleanup when client disconnects
      request.signal.addEventListener('abort', () => {
        console.log('[MQTT SSE] Client disconnected, closing MQTT');
        client.end();
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
