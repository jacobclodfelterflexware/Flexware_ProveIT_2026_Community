import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    timestamp: Date.now(),
    service: 'mqtt-topic-tree',
    version: '1.0.0',
  });
}

export const dynamic = 'force-dynamic';
