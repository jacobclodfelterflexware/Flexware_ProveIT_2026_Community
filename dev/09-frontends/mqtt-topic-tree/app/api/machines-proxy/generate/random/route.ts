import { NextRequest, NextResponse } from 'next/server';

const MACHINE_SIMULATOR_URL = process.env.MACHINE_SIMULATOR_URL || 'http://YOUR_MACHINE_SIMULATOR_HOST:YOUR_API_PORT_3';

export async function POST(request: NextRequest) {
  const url = `${MACHINE_SIMULATOR_URL}/api/machines/generate/random`;
  const startTime = Date.now();

  console.log('[MachinesProxy] Starting random machine generation request...');

  try {
    const body = await request.text();

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body || '{}',
    });

    const elapsed = Date.now() - startTime;
    console.log(`[MachinesProxy] Backend responded in ${elapsed}ms, status: ${response.status}`);

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    const elapsed = Date.now() - startTime;
    console.error(`[MachinesProxy] Generate random error after ${elapsed}ms:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to machine simulator service' },
      { status: 503 }
    );
  }
}

export const dynamic = 'force-dynamic';
