import { NextRequest, NextResponse } from 'next/server';

const CHART_ENGINE_URL = process.env.CHART_ENGINE_URL || 'http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3';

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${CHART_ENGINE_URL}/api/skills`);
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[Chart Engine Proxy] Skills error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch skills' },
      { status: 503 }
    );
  }
}

export const dynamic = 'force-dynamic';
