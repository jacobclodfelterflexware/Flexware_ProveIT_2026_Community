import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';
import { randomUUID } from 'crypto';

/**
 * GET /api/schemas/bindings
 * List all topic bindings
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const proposalId = searchParams.get('proposalId');
  const topicPath = searchParams.get('topicPath');

  const session = getSession();

  try {
    // Build WHERE clause
    const conditions: string[] = [];
    const params: Record<string, unknown> = {};

    if (proposalId) {
      conditions.push('tb.proposalId = $proposalId');
      params.proposalId = proposalId;
    }
    if (topicPath) {
      conditions.push('tb.topicPath = $topicPath');
      params.topicPath = topicPath;
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    const query = `
      MATCH (tb:TopicBinding)
      ${whereClause}
      OPTIONAL MATCH (sp:SchemaProposal {id: tb.proposalId})
      RETURN tb {
        .id, .topicPath, .proposalId, .boundBy,
        boundAt: toString(tb.boundAt)
      } AS binding,
      sp.name AS proposalName
      ORDER BY tb.topicPath
    `;

    const result = await session.run(query, params);

    const bindings = result.records.map(r => ({
      ...r.get('binding'),
      proposalName: r.get('proposalName')
    }));

    return NextResponse.json({ bindings });
  } catch (error) {
    console.error('Error fetching bindings:', error);
    return NextResponse.json(
      { error: 'Failed to fetch bindings' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * POST /api/schemas/bindings
 * Create a new topic binding
 */
export async function POST(request: NextRequest) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { topicPath, proposalId } = body;

  if (!topicPath) {
    return NextResponse.json({ error: 'topicPath is required' }, { status: 400 });
  }
  if (!proposalId) {
    return NextResponse.json({ error: 'proposalId is required' }, { status: 400 });
  }

  const session = getSession();

  try {
    // Check if proposal exists
    const checkProposalQuery = `
      MATCH (sp:SchemaProposal {id: $proposalId})
      RETURN sp.id AS id
    `;
    const proposalResult = await session.run(checkProposalQuery, { proposalId });

    if (proposalResult.records.length === 0) {
      return NextResponse.json(
        { error: 'Proposal not found' },
        { status: 404 }
      );
    }

    // Check if binding already exists for this topic
    const checkBindingQuery = `
      MATCH (tb:TopicBinding {topicPath: $topicPath})
      RETURN tb.id AS id, tb.proposalId AS existingProposalId
    `;
    const existingResult = await session.run(checkBindingQuery, { topicPath });

    if (existingResult.records.length > 0) {
      const existingProposalId = existingResult.records[0].get('existingProposalId');
      return NextResponse.json(
        {
          error: 'Topic already has a binding',
          existingProposalId
        },
        { status: 409 }
      );
    }

    // Create the binding
    const id = randomUUID();
    const createQuery = `
      CREATE (tb:TopicBinding {
        id: $id,
        topicPath: $topicPath,
        proposalId: $proposalId,
        boundAt: datetime(),
        boundBy: $boundBy
      })
      RETURN tb.id AS id
    `;

    const result = await session.run(createQuery, {
      id,
      topicPath,
      proposalId,
      boundBy: 'user' // TODO: Get from auth
    });

    const createdId = result.records[0]?.get('id');

    return NextResponse.json({
      success: true,
      id: createdId
    });
  } catch (error) {
    console.error('Error creating binding:', error);
    return NextResponse.json(
      { error: 'Failed to create binding' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * DELETE /api/schemas/bindings
 * Delete a binding by topic path
 */
export async function DELETE(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('topicPath');
  const bindingId = searchParams.get('id');

  if (!topicPath && !bindingId) {
    return NextResponse.json(
      { error: 'topicPath or id is required' },
      { status: 400 }
    );
  }

  const session = getSession();

  try {
    let query: string;
    let params: Record<string, unknown>;

    if (bindingId) {
      query = `
        MATCH (tb:TopicBinding {id: $id})
        DELETE tb
        RETURN count(*) AS deleted
      `;
      params = { id: bindingId };
    } else {
      query = `
        MATCH (tb:TopicBinding {topicPath: $topicPath})
        DELETE tb
        RETURN count(*) AS deleted
      `;
      params = { topicPath };
    }

    const result = await session.run(query, params);
    const deleted = result.records[0]?.get('deleted')?.toNumber() || 0;

    if (deleted === 0) {
      return NextResponse.json(
        { error: 'Binding not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting binding:', error);
    return NextResponse.json(
      { error: 'Failed to delete binding' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}
