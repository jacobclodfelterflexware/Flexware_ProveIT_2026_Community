// POST /api/view-transform - Generate or retrieve a view transform for a topic
// GET /api/view-transform?path=<topic_path> - Get existing transform

import { NextRequest, NextResponse } from 'next/server';

const ML_PREDICTOR_URL = process.env.ML_PREDICTOR_URL || 'http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3';

export interface FieldMapping {
  source: string;
  target: string;
  type: string;
  description?: string;
}

export interface ViewTransformSchema {
  machineId: string;
  machineName: string;
  machineType?: string;
  description?: string;
  fieldMappings: FieldMapping[];
  numericFields: string[];
  primaryMetric?: string;
}

export interface ViewTransform {
  transformId: string;
  sourceTopicPath: string;
  schema: ViewTransformSchema;
  createdAt?: string;
  createdBy: string;
  promptVersion: string;
}

export interface TopicStructure {
  topicPath: string;
  isAggregated?: boolean;
  payload?: Record<string, unknown>;
  numericFields?: string[];
  childTopics?: string[];
  childPayloads?: Record<string, Record<string, unknown>>;
}

export interface GenerateTransformRequest {
  topicStructure: TopicStructure;
}

export interface GenerateTransformResponse {
  transform: ViewTransform;
  cached: boolean;
}

/**
 * GET - Retrieve existing transform for a topic
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('path');

  if (!topicPath) {
    return NextResponse.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

  try {
    const response = await fetch(
      `${ML_PREDICTOR_URL}/api/transforms/${encodeURIComponent(topicPath)}`,
      {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    if (response.status === 404) {
      return NextResponse.json(
        { error: 'No transform found for this topic', exists: false },
        { status: 404 }
      );
    }

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error);
    }

    const transform = await response.json();
    return NextResponse.json({ transform, exists: true });
  } catch (error) {
    console.error('[View Transform API] GET error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch transform', details: (error as Error).message },
      { status: 500 }
    );
  }
}

/**
 * POST - Generate a new transform (or return cached)
 */
export async function POST(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const forceRegenerate = searchParams.get('force') === 'true';

  try {
    const body: GenerateTransformRequest = await request.json();

    if (!body.topicStructure?.topicPath) {
      return NextResponse.json(
        { error: 'Missing required field: topicStructure.topicPath' },
        { status: 400 }
      );
    }

    const response = await fetch(
      `${ML_PREDICTOR_URL}/api/transforms/generate?force_regenerate=${forceRegenerate}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error);
    }

    const result: GenerateTransformResponse = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('[View Transform API] POST error:', error);
    return NextResponse.json(
      { error: 'Failed to generate transform', details: (error as Error).message },
      { status: 500 }
    );
  }
}

/**
 * DELETE - Remove a transform for a topic
 */
export async function DELETE(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('path');

  if (!topicPath) {
    return NextResponse.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

  try {
    const response = await fetch(
      `${ML_PREDICTOR_URL}/api/transforms/${encodeURIComponent(topicPath)}`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error);
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('[View Transform API] DELETE error:', error);
    return NextResponse.json(
      { error: 'Failed to delete transform', details: (error as Error).message },
      { status: 500 }
    );
  }
}

export const dynamic = 'force-dynamic';
