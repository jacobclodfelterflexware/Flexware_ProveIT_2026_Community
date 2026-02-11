// GET /api/graph/hierarchical-topics
// Proxies to uncurated-ingestor's hierarchical topics search
// Returns topics that share parent segments (structural siblings/cousins)
import { NextRequest, NextResponse } from 'next/server';

const INGESTOR_URL = process.env.UNCURATED_INGESTOR_URL ||
  'http://unYOUR_CURATED_INGESTOR_HOST:YOUR_API_PORT';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topic = searchParams.get('topic');
  const k = parseInt(searchParams.get('k') || '20', 10);

  if (!topic) {
    return NextResponse.json(
      { error: 'Missing required query parameter topic' },
      { status: 400 }
    );
  }

  try {
    console.log(`[Hierarchical Topics] Fetching siblings for: ${topic}`);

    const response = await fetch(
      `${INGESTOR_URL}/api/hierarchical-topics?topic=${encodeURIComponent(topic)}&k=${k}`,
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Hierarchical Topics] Ingestor error:', errorText);
      return NextResponse.json(
        { error: 'Hierarchical topics search failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log(`[Hierarchical Topics] Found ${data.count || 0} related topics`);

    return NextResponse.json(data);
  } catch (error) {
    console.error('[Hierarchical Topics] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch hierarchical topics', details: (error as Error).message },
      { status: 500 }
    );
  }
}

export const dynamic = 'force-dynamic';
