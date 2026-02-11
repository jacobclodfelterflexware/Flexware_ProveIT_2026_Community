import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

interface RouteParams {
  params: Promise<{ id: string }>;
}

/**
 * GET /api/schemas/proposals/[id]
 * Get a single schema proposal by ID
 */
export async function GET(
  request: NextRequest,
  { params }: RouteParams
) {
  const { id } = await params;
  const session = getSession();

  try {
    const query = `
      MATCH (sp:SchemaProposal {id: $id})
      OPTIONAL MATCH (tb:TopicBinding {proposalId: $id})
      WITH sp, collect(tb.topicPath) AS boundTopics
      RETURN sp {
        .id, .name, .folder, .description, .expectedSchema,
        .version, .createdBy,
        createdAt: toString(sp.createdAt),
        updatedAt: toString(sp.updatedAt)
      } AS proposal,
      boundTopics
    `;

    const result = await session.run(query, { id });
    const record = result.records[0];

    if (!record) {
      return NextResponse.json(
        { error: 'Proposal not found' },
        { status: 404 }
      );
    }

    const proposal = record.get('proposal');
    const boundTopics = record.get('boundTopics') as string[];

    return NextResponse.json({
      ...proposal,
      expectedSchema: proposal.expectedSchema ? JSON.parse(proposal.expectedSchema) : {},
      boundTopics
    });
  } catch (error) {
    console.error('Error fetching proposal:', error);
    return NextResponse.json(
      { error: 'Failed to fetch proposal' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * PUT /api/schemas/proposals/[id]
 * Update a schema proposal
 */
export async function PUT(
  request: NextRequest,
  { params }: RouteParams
) {
  const { id } = await params;

  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { name, folder, description, expectedSchema } = body;

  const session = getSession();

  try {
    // Build SET clause dynamically
    const setClauses: string[] = ['sp.updatedAt = datetime()', 'sp.version = sp.version + 1'];
    const setParams: Record<string, unknown> = { id };

    if (name !== undefined) {
      setClauses.push('sp.name = $name');
      setParams.name = name;
    }
    if (folder !== undefined) {
      setClauses.push('sp.folder = $folder');
      setParams.folder = folder;
    }
    if (description !== undefined) {
      setClauses.push('sp.description = $description');
      setParams.description = description;
    }
    if (expectedSchema !== undefined) {
      setClauses.push('sp.expectedSchema = $expectedSchema');
      setParams.expectedSchema = JSON.stringify(expectedSchema);
    }

    const query = `
      MATCH (sp:SchemaProposal {id: $id})
      SET ${setClauses.join(', ')}
      RETURN sp.id AS id, sp.version AS version
    `;

    const result = await session.run(query, setParams);
    const record = result.records[0];

    if (!record) {
      return NextResponse.json(
        { error: 'Proposal not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      id: record.get('id'),
      version: record.get('version').toNumber()
    });
  } catch (error) {
    console.error('Error updating proposal:', error);
    return NextResponse.json(
      { error: 'Failed to update proposal' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * DELETE /api/schemas/proposals/[id]
 * Delete a schema proposal and its bindings
 */
export async function DELETE(
  request: NextRequest,
  { params }: RouteParams
) {
  const { id } = await params;
  const session = getSession();

  try {
    // First delete all bindings that reference this proposal
    const deleteBindingsQuery = `
      MATCH (tb:TopicBinding {proposalId: $id})
      DELETE tb
      RETURN count(*) AS deletedBindings
    `;

    // Then delete the proposal
    const deleteProposalQuery = `
      MATCH (sp:SchemaProposal {id: $id})
      DELETE sp
      RETURN count(*) AS deleted
    `;

    const bindingsResult = await session.run(deleteBindingsQuery, { id });
    const deletedBindings = bindingsResult.records[0]?.get('deletedBindings')?.toNumber() || 0;

    const result = await session.run(deleteProposalQuery, { id });
    const deleted = result.records[0]?.get('deleted')?.toNumber() || 0;

    if (deleted === 0) {
      return NextResponse.json(
        { error: 'Proposal not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      deletedBindings
    });
  } catch (error) {
    console.error('Error deleting proposal:', error);
    return NextResponse.json(
      { error: 'Failed to delete proposal' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}
