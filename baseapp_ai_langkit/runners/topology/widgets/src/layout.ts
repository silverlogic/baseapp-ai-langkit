// Pure data layer for the widget: topology JSON → ReactFlow nodes/edges,
// plus dagre top-to-bottom auto-layout. Has zero React dependencies so it
// stays trivially unit-testable under vitest.

import dagre from 'dagre';
import type { Edge as RFEdge, Node as RFNode } from 'reactflow';

import type {
  SidebarPrompt,
  TopologyEdge,
  TopologyEdgeKind,
  TopologyModel,
  TopologyNode,
  TopologyNodeKind,
  TopologyResponse,
} from './types';

export interface GraphNodeData {
  key: string;
  class_name: string;
  kind: TopologyNodeKind;
  model: TopologyModel;
  prompts: SidebarPrompt[];
  // True iff at least one prompt on this node has a non-empty admin override,
  // OR the model has an override row. Drives the "overridden" badge.
  has_override: boolean;
}

export interface GraphEdgeData {
  kind: TopologyEdgeKind;
}

export type GraphNode = RFNode<GraphNodeData>;
export type GraphEdge = RFEdge<GraphEdgeData>;

const NODE_WIDTH = 220;
const NODE_HEIGHT = 64;
// Wider separations than dagre's defaults so fan-out children sit far enough
// apart that a skip-rank edge (e.g. orchestrator → synthesizer) clears the
// middle-rank nodes instead of painting through them. Bumping ranksep also
// helps the dagre-injected dummy nodes route long edges around obstacles.
const RANK_SEP = 110;
const NODE_SEP = 90;
const EDGE_SEP = 30;

// CSS selector ReactFlow uses to scope drag detection to a small handle.
// Anything outside this selector inside a node fires onNodeClick instead of
// initiating drag — that's the "click opens sidebar" path.
export const NODE_DRAG_HANDLE_SELECTOR = '.rtw-node__grip';

export function nodeHasOverride(node: TopologyNode): boolean {
  if (node.usage_prompt?.override?.text) return true;
  for (const sm of node.state_modifier_prompts ?? []) {
    if (sm.override?.text) return true;
  }
  if (node.model?.override) return true;
  return false;
}

// Fallback used when the topology payload's per-node `model` field is missing
// (older fixtures pre-S02). The runtime server contract always emits a model
// object, so this branch only fires in tests.
const NULL_MODEL: TopologyModel = {
  initializer_key: null,
  model_id: null,
  params: {},
  override: null,
};

export function buildSidebarPrompts(node: TopologyNode): SidebarPrompt[] {
  const out: SidebarPrompt[] = [];
  if (node.usage_prompt) {
    out.push({
      role: 'usage',
      label: 'Usage prompt',
      prompt: node.usage_prompt,
    });
  }
  for (const sm of node.state_modifier_prompts ?? []) {
    const { key, ...prompt } = sm;
    out.push({
      role: 'state_modifier',
      label: `State modifier — ${key}`,
      prompt,
      state_modifier_key: key,
    });
  }
  return out;
}

export function topologyToGraph(payload: TopologyResponse): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const declaredKeys = new Set(payload.nodes.map((n) => n.key));

  const nodes: GraphNode[] = payload.nodes.map((n) => ({
    id: n.key,
    type: n.kind,
    position: { x: 0, y: 0 },
    // Drag only initiates from `.rtw-node__grip`; clicks elsewhere on the
    // node still fire `onNodeClick` (which opens the sidebar).
    dragHandle: NODE_DRAG_HANDLE_SELECTOR,
    data: {
      key: n.key,
      class_name: n.class_name,
      kind: n.kind,
      model: n.model ?? NULL_MODEL,
      prompts: buildSidebarPrompts(n),
      has_override: nodeHasOverride(n),
    },
  }));

  const edges: GraphEdge[] = payload.edges
    .filter((e) => declaredKeys.has(e.source) && declaredKeys.has(e.target))
    .map((e) => _toRfEdge(e));

  return { nodes, edges };
}

function _toRfEdge(e: TopologyEdge): GraphEdge {
  return {
    id: `${e.source}->${e.target}-${e.kind}`,
    source: e.source,
    target: e.target,
    type: e.kind,
    data: { kind: e.kind },
  };
}

export function applyDagreLayout(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  if (nodes.length === 0) return nodes;

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: 'TB',
    nodesep: NODE_SEP,
    ranksep: RANK_SEP,
    edgesep: EDGE_SEP,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);

  // Center-based positions, keyed by node id, so the conflict resolver can
  // mutate them in place before we hand them back to ReactFlow.
  const positions = new Map<string, { x: number; y: number }>();
  for (const n of nodes) {
    const placed = g.node(n.id);
    positions.set(n.id, { x: placed.x, y: placed.y });
  }

  _balanceFanOutChildren(edges, positions);
  _nudgeNodesOffSkipRankEdges(nodes, edges, positions);

  return nodes.map((n) => {
    const pos = positions.get(n.id)!;
    return {
      ...n,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
    };
  });
}

// Re-center the direct children of every fan-out parent around the parent's
// X. Dagre's barycenter ordering can produce visibly asymmetric layouts when
// a parent has multiple children AND a skip-rank edge to a deeper node — the
// dummy node dagre inserts for the skip-rank edge competes with the real
// children for position. The user only sees "one child looks far away, the
// other looks close." This pass restores symmetry.
//
// Like the nudge pass, this is purely geometric — it groups by edge
// adjacency (source → target with reasonable rank distance), no node names
// or kinds involved.
function _balanceFanOutChildren(
  edges: GraphEdge[],
  positions: Map<string, { x: number; y: number }>,
): void {
  const ADJACENT_RANK_MIN_DY = NODE_HEIGHT * 0.8;
  const ADJACENT_RANK_MAX_DY = NODE_HEIGHT * 3; // forgiving — long edges still count
  const SAME_RANK_Y_TOLERANCE = NODE_HEIGHT * 0.5;
  const SHIFT_NOISE_FLOOR = 5; // ignore sub-pixel asymmetry

  const childrenByParent = new Map<string, Set<string>>();
  for (const edge of edges) {
    const sp = positions.get(edge.source);
    const tp = positions.get(edge.target);
    if (!sp || !tp) continue;
    const dy = tp.y - sp.y;
    if (dy < ADJACENT_RANK_MIN_DY || dy > ADJACENT_RANK_MAX_DY) continue;
    const set = childrenByParent.get(edge.source) ?? new Set<string>();
    set.add(edge.target);
    childrenByParent.set(edge.source, set);
  }

  for (const [parentId, childSet] of childrenByParent) {
    if (childSet.size < 2) continue;
    const parent = positions.get(parentId);
    if (!parent) continue;
    const childIds = Array.from(childSet);
    const childPositions = childIds
      .map((id) => positions.get(id))
      .filter((p): p is { x: number; y: number } => p !== undefined);
    if (childPositions.length < 2) continue;

    // Only balance children that share a rank (same Y). Mixing ranks would
    // wreck unrelated layouts.
    const firstY = childPositions[0].y;
    if (
      !childPositions.every(
        (c) => Math.abs(c.y - firstY) < SAME_RANK_Y_TOLERANCE,
      )
    ) {
      continue;
    }

    const meanX =
      childPositions.reduce((acc, c) => acc + c.x, 0) / childPositions.length;
    const shift = parent.x - meanX;
    if (Math.abs(shift) < SHIFT_NOISE_FLOOR) continue;
    for (const childId of childIds) {
      const cp = positions.get(childId);
      if (cp) cp.x += shift;
    }
  }
}

// Post-processing pass: if a node sits on (or near) the straight line that a
// skip-rank edge would draw between its source and target, nudge it just far
// enough sideways to clear the edge's lane.
//
// The algorithm is workflow-agnostic — it looks at node positions and edge
// endpoints (purely geometric), not at node names, kinds, or labels. The
// thresholds are scaled by NODE_WIDTH / NODE_HEIGHT so the same code works
// for graphs of any size or fan-out shape. Drag-and-drop is the manual
// escape hatch when this heuristic misses.
//
// Nudge size = (half-node-width + 6) − |currentDistance| + 6 clearance, so a
// dead-center conflict ends ~12 px outside the node edge from the line —
// close to natural placement, not pushed across the canvas.
function _nudgeNodesOffSkipRankEdges(
  nodes: GraphNode[],
  edges: GraphEdge[],
  positions: Map<string, { x: number; y: number }>,
): void {
  const SKIP_RANK_Y_THRESHOLD = NODE_HEIGHT * 1.5; // edge must span > 1 rank
  const RANK_Y_TOLERANCE = NODE_HEIGHT * 0.6; // exclude nodes at source/target rank
  // Only flag a conflict when the edge passes *through* the node body, not
  // when it grazes the edge. 0.4 × NODE_WIDTH = 88 px means the line must be
  // within the central 80% of the node before we move it. Nodes already
  // off to a side (e.g., one of several fan-out children of a parent) stay
  // put — they were never blocking the edge to begin with.
  const CONFLICT_X_TOLERANCE = NODE_WIDTH * 0.4;
  // Post-nudge clearance: the node ends ~(NODE_WIDTH/2 + 8)px from the line,
  // i.e., 8px outside its own edge. Just enough to read clearly.
  const NUDGE_GAP = 30;

  for (const edge of edges) {
    const sp = positions.get(edge.source);
    const tp = positions.get(edge.target);
    if (!sp || !tp) continue;

    const dy = tp.y - sp.y;
    if (Math.abs(dy) < SKIP_RANK_Y_THRESHOLD) continue;

    const yMin = Math.min(sp.y, tp.y) + RANK_Y_TOLERANCE;
    const yMax = Math.max(sp.y, tp.y) - RANK_Y_TOLERANCE;

    for (const node of nodes) {
      if (node.id === edge.source || node.id === edge.target) continue;
      const np = positions.get(node.id);
      if (!np) continue;
      if (np.y < yMin || np.y > yMax) continue;

      const t = (np.y - sp.y) / dy;
      const lineX = sp.x + t * (tp.x - sp.x);
      const distance = np.x - lineX;
      const absDistance = Math.abs(distance);
      if (absDistance >= CONFLICT_X_TOLERANCE) continue;

      // Direction: keep the node on whichever side it's already biased to;
      // dead-center hit defaults to the right for deterministic layouts.
      const naturalDir = distance >= 0 ? 1 : -1;
      const magnitude = CONFLICT_X_TOLERANCE - absDistance + NUDGE_GAP;

      // Collision-aware: if the natural-side nudge would overlap a sibling at
      // the same rank, try the opposite side. If both sides are blocked
      // (e.g., the middle of 3 fan-out children with neighbors on both
      // flanks), leave the node and accept that the edge passes through it
      // — better than two nodes overlapping.
      const newPos = _firstNonCollidingNudge(
        node.id,
        np,
        nodes,
        positions,
        magnitude,
        naturalDir,
      );
      if (newPos !== null) np.x = newPos;
    }
  }
}

function _firstNonCollidingNudge(
  selfId: string,
  selfPos: { x: number; y: number },
  nodes: GraphNode[],
  positions: Map<string, { x: number; y: number }>,
  magnitude: number,
  naturalDir: number,
): number | null {
  const Y_TOLERANCE = NODE_HEIGHT * 0.7;
  const MIN_NEIGHBOR_GAP = NODE_WIDTH + 24;
  for (const dir of [naturalDir, -naturalDir]) {
    const candidateX = selfPos.x + dir * magnitude;
    let collides = false;
    for (const other of nodes) {
      if (other.id === selfId) continue;
      const op = positions.get(other.id);
      if (!op) continue;
      if (Math.abs(op.y - selfPos.y) > Y_TOLERANCE) continue;
      if (Math.abs(op.x - candidateX) < MIN_NEIGHBOR_GAP) {
        collides = true;
        break;
      }
    }
    if (!collides) return candidateX;
  }
  return null;
}

export function layoutTopology(payload: TopologyResponse): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const { nodes, edges } = topologyToGraph(payload);

  // Persisted layout: when every declared node carries a numeric position,
  // skip dagre (and the balance/nudge post-processors) entirely. Partial
  // persistence falls back to full auto-layout — keeps the algorithm
  // predictable; admin re-saves when new nodes appear in code.
  const allPersisted =
    payload.nodes.length > 0 &&
    payload.nodes.every(
      (n) =>
        n.position &&
        typeof n.position.x === 'number' &&
        typeof n.position.y === 'number',
    );
  if (allPersisted) {
    const byKey = new Map(payload.nodes.map((n) => [n.key, n.position!] as const));
    return {
      nodes: nodes.map((n) => {
        const p = byKey.get(n.id)!;
        return { ...n, position: { x: p.x, y: p.y } };
      }),
      edges,
    };
  }

  return { nodes: applyDagreLayout(nodes, edges), edges };
}

export function payloadHasPersistedPositions(payload: TopologyResponse): boolean {
  return payload.nodes.some(
    (n) =>
      n.position &&
      typeof n.position.x === 'number' &&
      typeof n.position.y === 'number',
  );
}
