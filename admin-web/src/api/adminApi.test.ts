import { AdminApi } from './adminApi'

describe('AdminApi', () => {
  it('only adds the in-memory bearer token to authenticated requests', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], limit: 100, offset: 0 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const api = new AdminApi(() => 'memory-only-token', vi.fn())

    await api.listAdminActors()

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer memory-only-token')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('does not send authorization credentials to the login endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          admin_actor_id: 'admin-1',
          access_token: 'new-token',
          expires_at: '2026-08-29T20:00:00Z',
          role_keys: ['admin_security'],
          permissions: ['admin:actor:read'],
        }),
        { status: 201, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const api = new AdminApi(() => 'old-token', vi.fn())

    await api.createSession('root.admin', 'Password-Long-Enough-2026!')

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.has('Authorization')).toBe(false)
  })

  it('clears the session boundary and exposes the stable error code on 401', async () => {
    const onUnauthorized = vi.fn()
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: 'admin_authentication_required',
            message: 'authentication required',
            request_id: 'req-expired',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const api = new AdminApi(() => 'expired-token', onUnauthorized)

    await expect(api.getMe()).rejects.toMatchObject({
      status: 401,
      code: 'admin_authentication_required',
      requestId: 'req-expired',
    })
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('uses operation intents for review decisions and keeps review history read-only', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            review_task_id: 'task-1',
            place_revision_id: 'revision-1',
            status: 'approved',
            assigned_reviewer_id: null,
            version: 2,
            created_by: 'admin-1',
            created_at: '2026-08-30T00:00:00Z',
            updated_at: '2026-08-30T00:01:00Z',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    const api = new AdminApi(() => 'memory-only-token', vi.fn())

    await api.decidePlaceReview('task-1', {
      expected_version: 1,
      decision_kind: 'approve',
      reason_code: 'OM1_FACTS_VERIFIED',
    })
    await api.listReviewDecisions('task-1')

    expect(fetchMock.mock.calls[0][0]).toContain('/review-tasks/task-1/decisions')
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as Record<string, unknown>
    expect(body.operation_intent_id).toEqual(expect.any(String))
    expect(fetchMock.mock.calls[1][0]).toContain('/review-tasks/task-1/decisions')
    expect(fetchMock.mock.calls[1][1]?.method).toBeUndefined()
  })

  it('submits reviewer evidence decisions to the revision-scoped endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ place_revision_id: 'revision-1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const api = new AdminApi(() => 'reviewer-token', vi.fn())

    await api.reviewEvidence('revision-1', 'geometry', 'geometry-1', {
      review_status: 'human_verified',
      operation_intent_id: 'evidence-review-1',
      reason_code: 'EVIDENCE_APPROVED',
    })

    expect(fetchMock.mock.calls[0][0]).toContain(
      '/place-revisions/revision-1/evidence/geometry/geometry-1/review',
    )
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST')
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      review_status: 'human_verified',
      operation_intent_id: 'evidence-review-1',
      reason_code: 'EVIDENCE_APPROVED',
    })
  })

  it('uses separate operation intents for publication batch preview and execution', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ batch_id: 'batch-1', items: [] }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ batch: { batch_id: 'batch-1' }, snapshot: null, reused: false }), { status: 200 }))
    const api = new AdminApi(() => 'publisher-token', vi.fn())
    await api.previewPublicationBatch({ city_id: 'hangzhou', place_revision_ids: ['revision-1'], operation_intent_id: 'preview-1', reason_code: 'BATCH_PREVIEW' })
    await api.executePublicationBatch('batch-1', { operation_intent_id: 'execute-1', reason_code: 'BATCH_EXECUTE' })
    expect(fetchMock.mock.calls[0][0]).toContain('/publication-batches/previews')
    expect(fetchMock.mock.calls[1][0]).toContain('/publication-batches/batch-1/execute')
  })

  it('prepares a candidate projection through the revision-scoped endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ projection_id: 'projection-1', gate_reason_codes: [] }), { status: 200 }))
    const api = new AdminApi(() => 'publisher-token', vi.fn())
    await api.preparePlaceRevisionProjection('revision-1', {
      data_snapshot_version: 'hangzhou-research-candidate-v1',
      solver_node_id: 1001,
      operation_intent_id: 'projection-prepare-1',
      reason_code: 'PROJECTION_PREPARED',
    })
    expect(fetchMock.mock.calls[0][0]).toContain('/place-revisions/revision-1/projection-preparations')
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST')
  })

  it('loads and resolves revision source conflicts with optimistic concurrency fields', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ revision_id: 'revision-1', items: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ place_revision_id: 'revision-1' }), { status: 200 }))
    const api = new AdminApi(() => 'editor-token', vi.fn())

    await api.listSourceConflicts('revision-1')
    await api.resolveSourceConflicts('revision-1', {
      expected_revision_number: 2,
      expected_revision_version: 4,
      resolved: true,
      operation_intent_id: 'conflict-resolve-1',
      reason_code: 'SOURCE_CONFLICTS_REVIEWED',
      reason_text: '以官方公告为准',
    })

    expect(fetchMock.mock.calls[0][0]).toContain('/place-revisions/revision-1/source-conflicts')
    expect(fetchMock.mock.calls[1][0]).toContain('/place-revisions/revision-1/source-conflicts/resolve')
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      expected_revision_number: 2,
      expected_revision_version: 4,
      resolved: true,
    })
  })
})
