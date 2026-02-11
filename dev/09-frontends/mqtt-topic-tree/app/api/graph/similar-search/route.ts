// GET /api/graph/similar-search
// Proxies to uncurated-ingestor's similarity search and transforms response
import { NextRequest, NextResponse } from 'next/server';

const INGESTOR_URL = process.env.UNCURATED_INGESTOR_URL ||
  'http://unYOUR_CURATED_INGESTOR_HOST:YOUR_API_PORT';

interface IngestorSimilarResult {
  topicPath: string;
  score: number;
  payloadText?: string;
  timestamp?: string;
}

interface SimilarResult {
  topic_path: string;
  similarity: number;
  field_names: string[];
  historical_payloads: Array<{
    payload: Record<string, unknown>;
    timestamp?: string;
  }>;
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get('q');
  const k = parseInt(searchParams.get('k') || '10', 10);

  if (!query) {
    return NextResponse.json(
      { error: 'Missing required query parameter q' },
      { status: 400 }
    );
  }

  try {
    // Request more results to ensure we get k unique topics after deduplication
    const requestK = Math.min(k * 5, 100);

    const response = await fetch(
      `${INGESTOR_URL}/api/similar-messages?q=${encodeURIComponent(query)}&k=${requestK}`,
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Similar Search API] Ingestor error:', errorText);
      return NextResponse.json(
        { error: 'Similarity search failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();

    // Deduplicate by topicPath, keeping highest similarity score for each unique topic
    const uniqueByTopic = new Map<string, IngestorSimilarResult>();
    for (const r of (data.results || []) as IngestorSimilarResult[]) {
      if (!r.topicPath) continue;
      const existing = uniqueByTopic.get(r.topicPath);
      if (!existing || r.score > existing.score) {
        uniqueByTopic.set(r.topicPath, r);
      }
    }

    // Take top k unique results sorted by similarity
    const uniqueResults = Array.from(uniqueByTopic.values())
      .sort((a, b) => b.score - a.score)
      .slice(0, k);

    // Transform to SimilarResult[] format expected by GraphVisualization
    const results: SimilarResult[] = uniqueResults.map((r) => ({
      topic_path: r.topicPath,
      similarity: r.score,
      field_names: [],
      historical_payloads: [{
        payload: { text: r.payloadText },
        timestamp: r.timestamp,
      }],
    }));

    return NextResponse.json({
      query: data.query,
      count: results.length,
      results,
    });
  } catch (error) {
    console.error('[Similar Search API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to perform similarity search', details: (error as Error).message },
      { status: 500 }
    );
  }
}

export const dynamic = 'force-dynamic';
