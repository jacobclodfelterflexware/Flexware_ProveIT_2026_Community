import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';
import { randomUUID } from 'crypto';

/**
 * GET /api/schemas/proposals
 * List schema proposals with optional filtering
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const folder = searchParams.get('folder');
  const search = searchParams.get('search');
  const page = parseInt(searchParams.get('page') || '1');
  const pageSize = parseInt(searchParams.get('pageSize') || '20');

  const session = getSession();

  try {
    // Build WHERE clause
    const conditions: string[] = [];
    const params: Record<string, unknown> = {
      skip: (page - 1) * pageSize,
      limit: pageSize
    };

    if (folder) {
      conditions.push('sp.folder = $folder');
      params.folder = folder;
    }
    if (search) {
      conditions.push('toLower(sp.name) CONTAINS toLower($search)');
      params.search = search;
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    // Query proposals
    const query = `
      MATCH (sp:SchemaProposal)
      ${whereClause}
      RETURN sp {
        .id, .name, .folder, .description, .expectedSchema,
        .version, .createdBy,
        createdAt: toString(sp.createdAt),
        updatedAt: toString(sp.updatedAt)
      } AS proposal
      ORDER BY sp.folder, sp.name
      SKIP $skip LIMIT $limit
    `;

    // Query distinct folders for navigation
    const foldersQuery = `
      MATCH (sp:SchemaProposal)
      RETURN DISTINCT sp.folder AS folder
      ORDER BY folder
    `;

    // Query total count
    const countQuery = `
      MATCH (sp:SchemaProposal)
      ${whereClause}
      RETURN count(sp) AS total
    `;

    const [proposalsResult, foldersResult, countResult] = await Promise.all([
      session.run(query, params),
      session.run(foldersQuery),
      session.run(countQuery, params)
    ]);

    const proposals = proposalsResult.records.map(r => {
      const p = r.get('proposal');
      return {
        ...p,
        expectedSchema: p.expectedSchema ? JSON.parse(p.expectedSchema) : {}
      };
    });

    const folders = foldersResult.records
      .map(r => r.get('folder'))
      .filter((f): f is string => Boolean(f));

    const total = countResult.records[0]?.get('total')?.toNumber() || 0;

    return NextResponse.json({
      proposals,
      folders,
      total,
      page,
      pageSize
    });
  } catch (error) {
    console.error('Error fetching proposals:', error);
    return NextResponse.json(
      { error: 'Failed to fetch proposals' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * POST /api/schemas/proposals
 * Create a new schema proposal
 */
export async function POST(request: NextRequest) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { name, folder, description, expectedSchema } = body;

  if (!name) {
    return NextResponse.json({ error: 'name is required' }, { status: 400 });
  }
  if (!expectedSchema) {
    return NextResponse.json({ error: 'expectedSchema is required' }, { status: 400 });
  }

  const session = getSession();

  try {
    const id = randomUUID();

    const query = `
      CREATE (sp:SchemaProposal {
        id: $id,
        name: $name,
        folder: $folder,
        description: $description,
        expectedSchema: $expectedSchema,
        version: 1,
        createdAt: datetime(),
        updatedAt: datetime(),
        createdBy: $createdBy
      })
      RETURN sp.id AS id
    `;

    const result = await session.run(query, {
      id,
      name,
      folder: folder || 'default',
      description: description || '',
      expectedSchema: JSON.stringify(expectedSchema),
      createdBy: 'user' // TODO: Get from auth
    });

    const createdId = result.records[0]?.get('id');

    return NextResponse.json({
      success: true,
      id: createdId
    });
  } catch (error) {
    console.error('Error creating proposal:', error);
    return NextResponse.json(
      { error: 'Failed to create proposal' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}
