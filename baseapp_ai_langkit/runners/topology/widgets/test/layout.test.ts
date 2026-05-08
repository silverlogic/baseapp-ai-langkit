import { describe, expect, it } from 'vitest';
import {
  applyDagreLayout,
  buildSidebarPrompts,
  layoutTopology,
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
});
