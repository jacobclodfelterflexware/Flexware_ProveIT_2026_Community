import { NextRequest, NextResponse } from 'next/server';

const CHART_ENGINE_URL = process.env.CHART_ENGINE_URL || 'http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3';

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();

    const response = await fetch(`${CHART_ENGINE_URL}/api/chart/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[Chart Engine Proxy] Generate error:', error);
    return NextResponse.json(
      { error: 'Failed to generate chart' },
      { status: 503 }
    );
  }
}

export const dynamic = 'force-dynamic';
