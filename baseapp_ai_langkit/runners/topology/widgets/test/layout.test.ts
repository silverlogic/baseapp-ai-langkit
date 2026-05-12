import { describe, expect, it } from 'vitest';
import {
  applyDagreLayout,
  buildSidebarPrompts,
  layoutTopology,
  NODE_DRAG_HANDLE_SELECTOR,
  payloadHasPersistedPositions,
  topologyToGraph,
} from '../src/layout';
import type { TopologyResponse } from '../src/types';

const linearChain: TopologyResponse = {
  nodes: [
    { key: 'A', class_name: 'AgentA', kind: 'agent' },
    { key: 'B', class_name: 'WorkerB', kind: 'worker' },
    { key: 'C', class_name: 'AgentC', kind: 'agent' },
  ],
  edges: [
    { source: 'A', target: 'B', kind: 'normal' },
    { source: 'B', target: 'C', kind: 'normal' },
  ],
};

const fanOut: TopologyResponse = {
  nodes: [
    { key: 'O', class_name: 'Orchestrator', kind: 'agent' },
    { key: 'X', class_name: 'AgentX', kind: 'agent' },
    { key: 'Y', class_name: 'AgentY', kind: 'agent' },
    { key: 'S', class_name: 'Synthesizer', kind: 'worker' },
  ],
  edges: [
    { source: 'O', target: 'X', kind: 'conditional' },
    { source: 'O', target: 'Y', kind: 'conditional' },
    { source: 'X', target: 'S', kind: 'normal' },
    { source: 'Y', target: 'S', kind: 'normal' },
  ],
};

describe('topologyToGraph', () => {
  it('returns RF nodes preserving identity, kind, and prompts', () => {
    const payload: TopologyResponse = {
      nodes: [
        {
          key: 'A',
          class_name: 'AgentA',
          kind: 'agent',
          model: { identifier: 'gpt-4o' },
          usage_prompt: {
            description: 'do the thing',
            required_placeholders: ['{input}'],
            default_text: 'default',
            override: { text: 'override', saved_at: '2026-05-08T12:00:00Z' },
          },
          state_modifier_prompts: [
            {
              key: 'shape_user_input',
              description: 'shape input',
              required_placeholders: [],
              default_text: 'sm default',
            },
          ],
        },
      ],
      edges: [],
    };
    const { nodes } = topologyToGraph(payload);
    expect(nodes).toHaveLength(1);
    const n = nodes[0];
    expect(n.id).toBe('A');
    expect(n.type).toBe('agent');
    expect(n.data.key).toBe('A');
    expect(n.data.class_name).toBe('AgentA');
    expect(n.data.kind).toBe('agent');
    expect(n.data.model?.identifier).toBe('gpt-4o');
    expect(n.data.prompts).toHaveLength(2);
    expect(n.data.prompts[0].role).toBe('usage');
    expect(n.data.prompts[1].role).toBe('state_modifier');
    expect(n.data.prompts[1].label).toContain('shape_user_input');
  });

  it('builds linear chain with normal edges', () => {
    const { nodes, edges } = topologyToGraph(linearChain);
    expect(nodes.map((n) => n.id)).toEqual(['A', 'B', 'C']);
    expect(edges).toHaveLength(2);
    expect(edges[0].type).toBe('normal');
    expect(edges[0].data?.kind).toBe('normal');
  });

  it('mixes agent and worker node types', () => {
    const { nodes } = topologyToGraph(linearChain);
    const types = nodes.map((n) => n.type);
    expect(types).toContain('agent');
    expect(types).toContain('worker');
  });

  it('marks conditional edges with type "conditional"', () => {
    const { edges } = topologyToGraph(fanOut);
    const conditional = edges.filter((e) => e.type === 'conditional');
    const normal = edges.filter((e) => e.type === 'normal');
    expect(conditional.length).toBe(2);
    expect(normal.length).toBe(2);
  });

  it('drops edges referencing keys that are not in declared nodes', () => {
    const payload: TopologyResponse = {
      nodes: [{ key: 'A', class_name: 'AgentA', kind: 'agent' }],
      edges: [
        { source: 'A', target: 'B', kind: 'normal' },
        { source: 'A', target: 'A', kind: 'normal' },
      ],
    };
    const { nodes, edges } = topologyToGraph(payload);
    expect(nodes).toHaveLength(1);
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe('A');
    expect(edges[0].target).toBe('A');
  });

  it('handles an empty topology', () => {
    const { nodes, edges } = topologyToGraph({ nodes: [], edges: [] });
    expect(nodes).toHaveLength(0);
    expect(edges).toHaveLength(0);
  });

  it('sets a dragHandle selector on each node so drag only fires from the grip', () => {
    const { nodes } = topologyToGraph(linearChain);
    expect(nodes).toHaveLength(3);
    for (const n of nodes) {
      expect(n.dragHandle).toBe(NODE_DRAG_HANDLE_SELECTOR);
    }
    expect(NODE_DRAG_HANDLE_SELECTOR).toMatch(/grip/);
  });

  it('flags has_override=true when the usage_prompt carries a non-empty override', () => {
    const payload: TopologyResponse = {
      nodes: [
        {
          key: 'X',
          class_name: 'X',
          kind: 'agent',
          usage_prompt: {
            description: 'd',
            required_placeholders: [],
            default_text: 'def',
            override: { text: 'over', saved_at: '2026-05-11' },
          },
        },
      ],
      edges: [],
    };
    expect(topologyToGraph(payload).nodes[0].data.has_override).toBe(true);
  });

  it('flags has_override=true when any state_modifier carries a non-empty override', () => {
    const payload: TopologyResponse = {
      nodes: [
        {
          key: 'X',
          class_name: 'X',
          kind: 'worker',
          state_modifier_prompts: [
            {
              key: '0',
              description: 'd',
              required_placeholders: [],
              default_text: 'def',
              override: null,
            },
            {
              key: '1',
              description: 'd',
              required_placeholders: [],
              default_text: 'def',
              override: { text: 'over', saved_at: '2026-05-11' },
            },
          ],
        },
      ],
      edges: [],
    };
    expect(topologyToGraph(payload).nodes[0].data.has_override).toBe(true);
  });

  it('flags has_override=false when override.text is empty (logically restored)', () => {
    const payload: TopologyResponse = {
      nodes: [
        {
          key: 'X',
          class_name: 'X',
          kind: 'agent',
          usage_prompt: {
            description: 'd',
            required_placeholders: [],
            default_text: 'def',
            override: { text: '', saved_at: '2026-05-11' },
          },
        },
      ],
      edges: [],
    };
    expect(topologyToGraph(payload).nodes[0].data.has_override).toBe(false);
  });

  it('balances asymmetric fan-out children so they sit symmetrically around the parent', () => {
    // Orchestrator with two children plus a skip-rank edge to the grandchild
    // is the case where dagre's barycenter ordering puts the dummy adjacent
    // to one child, pulling the layout off-center. The balancer should
    // restore symmetry by recentering the two children around O.x.
    const payload: TopologyResponse = {
      nodes: [
        { key: 'O', class_name: 'O', kind: 'worker' },
        { key: 'L', class_name: 'L', kind: 'worker' },
        { key: 'R', class_name: 'R', kind: 'worker' },
        { key: 'S', class_name: 'S', kind: 'worker' },
      ],
      edges: [
        { source: 'O', target: 'L', kind: 'normal' },
        { source: 'O', target: 'R', kind: 'normal' },
        { source: 'L', target: 'S', kind: 'normal' },
        { source: 'R', target: 'S', kind: 'normal' },
        { source: 'O', target: 'S', kind: 'normal' }, // skip-rank
      ],
    };
    const { nodes } = layoutTopology(payload);
    const o = nodes.find((n) => n.id === 'O')!;
    const l = nodes.find((n) => n.id === 'L')!;
    const r = nodes.find((n) => n.id === 'R')!;
    // Center-X of each: position.x is top-left, so center = position.x + 110.
    const oCenter = o.position.x + 110;
    const lCenter = l.position.x + 110;
    const rCenter = r.position.x + 110;
    // After balancing, L and R should sit symmetrically: their mean equals O.
    const childrenMean = (lCenter + rCenter) / 2;
    expect(Math.abs(childrenMean - oCenter)).toBeLessThan(6);
  });

  it('nudges a middle node off a skip-rank edge that would pass through it', () => {
    // A → B (rank 1) → C, plus A → C (rank-skipping). Dagre's default layout
    // centers B between A and C, putting it directly on the A→C path. The
    // post-processor should detect that and move B sideways.
    const payload: TopologyResponse = {
      nodes: [
        { key: 'A', class_name: 'A', kind: 'agent' },
        { key: 'B', class_name: 'B', kind: 'worker' },
        { key: 'C', class_name: 'C', kind: 'worker' },
      ],
      edges: [
        { source: 'A', target: 'B', kind: 'normal' },
        { source: 'B', target: 'C', kind: 'normal' },
        { source: 'A', target: 'C', kind: 'normal' },
      ],
    };
    const { nodes } = layoutTopology(payload);
    const a = nodes.find((n) => n.id === 'A')!;
    const b = nodes.find((n) => n.id === 'B')!;
    const c = nodes.find((n) => n.id === 'C')!;
    // The straight A→C path at B's Y.
    const t = (b.position.y - a.position.y) / (c.position.y - a.position.y);
    const lineX = a.position.x + t * (c.position.x - a.position.x);
    // B's center must clear that line by more than half a node width.
    const halfNode = 110; // NODE_WIDTH / 2
    expect(Math.abs(b.position.x + halfNode - (lineX + halfNode))).toBeGreaterThan(
      halfNode * 0.9,
    );
  });

  it('flags has_override=false when no overrides exist anywhere', () => {
    const payload: TopologyResponse = {
      nodes: [
        {
          key: 'X',
          class_name: 'X',
          kind: 'agent',
          usage_prompt: {
            description: 'd',
            required_placeholders: [],
            default_text: 'def',
            override: null,
          },
          state_modifier_prompts: [
            {
              key: '0',
              description: 'd',
              required_placeholders: [],
              default_text: 'def',
              override: null,
            },
          ],
        },
      ],
      edges: [],
    };
    expect(topologyToGraph(payload).nodes[0].data.has_override).toBe(false);
  });

  it('still maps when the payload carries an error (caller branches separately)', () => {
    const payload: TopologyResponse = {
      nodes: [],
      edges: [],
      error: { code: 'workflow_init_failed', message: 'kaboom' },
    };
    const { nodes, edges } = topologyToGraph(payload);
    expect(nodes).toHaveLength(0);
    expect(edges).toHaveLength(0);
  });
});

describe('buildSidebarPrompts', () => {
  it('returns no prompts when neither usage nor state-modifier exist', () => {
    expect(
      buildSidebarPrompts({ key: 'X', class_name: 'X', kind: 'agent' }),
    ).toEqual([]);
  });

  it('orders the usage prompt before any state-modifier prompts', () => {
    const out = buildSidebarPrompts({
      key: 'X',
      class_name: 'X',
      kind: 'agent',
      usage_prompt: {
        description: 'u',
        required_placeholders: [],
        default_text: 'u-default',
      },
      state_modifier_prompts: [
        {
          key: 'sm',
          description: 's',
          required_placeholders: [],
          default_text: 's-default',
        },
      ],
    });
    expect(out.map((p) => p.role)).toEqual(['usage', 'state_modifier']);
  });
});

describe('applyDagreLayout', () => {
  it('returns positioned nodes for a linear chain (top-to-bottom)', () => {
    const { nodes, edges } = topologyToGraph(linearChain);
    const positioned = applyDagreLayout(nodes, edges);
    expect(positioned).toHaveLength(3);
    // top-to-bottom: A's y < B's y < C's y
    const yA = positioned.find((n) => n.id === 'A')!.position.y;
    const yB = positioned.find((n) => n.id === 'B')!.position.y;
    const yC = positioned.find((n) => n.id === 'C')!.position.y;
    expect(yA).toBeLessThan(yB);
    expect(yB).toBeLessThan(yC);
  });

  it('is deterministic for the same input', () => {
    const { nodes, edges } = topologyToGraph(fanOut);
    const a = applyDagreLayout(nodes, edges);
    const b = applyDagreLayout(nodes, edges);
    expect(a.map((n) => [n.id, n.position.x, n.position.y])).toEqual(
      b.map((n) => [n.id, n.position.x, n.position.y]),
    );
  });

  it('returns the input unchanged when there are no nodes', () => {
    expect(applyDagreLayout([], [])).toEqual([]);
  });
});

describe('layoutTopology', () => {
  it('combines mapping and layout end-to-end', () => {
    const out = layoutTopology(linearChain);
    expect(out.nodes).toHaveLength(3);
    expect(out.edges).toHaveLength(2);
    expect(out.nodes.every((n) => Number.isFinite(n.position.y))).toBe(true);
  });

  it('uses persisted positions verbatim when every node carries one', () => {
    const payload: TopologyResponse = {
      nodes: [
        { key: 'A', class_name: 'A', kind: 'agent', position: { x: 500, y: 10 } },
        { key: 'B', class_name: 'B', kind: 'worker', position: { x: 200, y: 250 } },
        { key: 'C', class_name: 'C', kind: 'worker', position: { x: 700, y: 600 } },
      ],
      edges: [{ source: 'A', target: 'B', kind: 'normal' }],
    };
    const { nodes } = layoutTopology(payload);
    expect(nodes.find((n) => n.id === 'A')!.position).toEqual({ x: 500, y: 10 });
    expect(nodes.find((n) => n.id === 'B')!.position).toEqual({ x: 200, y: 250 });
    expect(nodes.find((n) => n.id === 'C')!.position).toEqual({ x: 700, y: 600 });
  });

  it('falls back to auto-layout when persistence is partial (only some nodes have positions)', () => {
    const payload: TopologyResponse = {
      nodes: [
        { key: 'A', class_name: 'A', kind: 'agent', position: { x: 500, y: 10 } },
        { key: 'B', class_name: 'B', kind: 'worker' }, // missing position
      ],
      edges: [{ source: 'A', target: 'B', kind: 'normal' }],
    };
    const { nodes } = layoutTopology(payload);
    // The persisted A position should not be honored because the layout
    // covered only one of the two nodes — dagre runs over everything to
    // keep the algorithm predictable.
    expect(nodes.find((n) => n.id === 'A')!.position).not.toEqual({ x: 500, y: 10 });
  });
});

describe('payloadHasPersistedPositions', () => {
  it('returns true when at least one node has a persisted position', () => {
    const payload: TopologyResponse = {
      nodes: [
        { key: 'A', class_name: 'A', kind: 'agent', position: { x: 10, y: 20 } },
        { key: 'B', class_name: 'B', kind: 'worker' },
      ],
      edges: [],
    };
    expect(payloadHasPersistedPositions(payload)).toBe(true);
  });

  it('returns false when no node has a persisted position', () => {
    const payload: TopologyResponse = {
      nodes: [{ key: 'A', class_name: 'A', kind: 'agent' }],
      edges: [],
    };
    expect(payloadHasPersistedPositions(payload)).toBe(false);
  });
});
