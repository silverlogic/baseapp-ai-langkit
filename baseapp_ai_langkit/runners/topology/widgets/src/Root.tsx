import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  EdgeProps,
  NodeProps,
  Panel,
  Position,
  getBezierPath,
  Handle,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

import type { GraphEdge, GraphEdgeData, GraphNode, GraphNodeData } from './layout';
import { layoutTopology } from './layout';
import { Sidebar } from './Sidebar';
import type {
  SidebarPrompt,
  TopologyError,
  TopologyResponse,
} from './types';
import { PromptEditModal } from './PromptEditModal';
import { DefaultPromptViewModal } from './DefaultPromptViewModal';
import { ModelEditModal } from './ModelEditModal';
import {
  buildSaveLayoutUrl,
  buildSavePromptUrl,
  saveTopologyLayout,
  type PromptSaveTarget,
} from './savePrompt';
import { buildSaveModelUrl } from './saveModel';

export interface RootProps {
  topologyUrl: string;
  legacyAdminUrl: string;
  // Optional: injectable fetch for tests. Defaults to window.fetch.
  fetchImpl?: typeof fetch;
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; error: TopologyError }
  | { status: 'ready'; payload: TopologyResponse };

const GENERIC_ERROR: TopologyError = {
  code: 'unknown',
  message: 'Failed to load the runner workflow.',
};

export function Root({ topologyUrl, legacyAdminUrl, fetchImpl }: RootProps) {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [selected, setSelected] = useState<GraphNodeData | null>(null);
  const [editing, setEditing] = useState<{
    node: GraphNodeData;
    prompt: SidebarPrompt;
  } | null>(null);
  const [viewingDefault, setViewingDefault] = useState<{
    node: GraphNodeData;
    prompt: SidebarPrompt;
  } | null>(null);
  const [editingModel, setEditingModel] = useState<GraphNodeData | null>(null);

  const refresh = useCallback(async () => {
    setState({ status: 'loading' });
    const result = await fetchTopology(topologyUrl, fetchImpl ?? window.fetch);
    if (_isError(result)) {
      setState({ status: 'error', error: result });
      return;
    }
    if (result.error) {
      setState({ status: 'error', error: result.error });
      return;
    }
    setState({ status: 'ready', payload: result });
  }, [topologyUrl, fetchImpl]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Keep the open sidebar's data in sync when the topology refreshes (e.g.,
  // after a successful save) so the user sees the new override immediately
  // without re-clicking the node.
  useEffect(() => {
    if (state.status !== 'ready' || !selected) return;
    const fresh = state.payload.nodes.find((n) => n.key === selected.key);
    if (!fresh) {
      setSelected(null);
      return;
    }
    const { nodes } = layoutTopology({ nodes: state.payload.nodes, edges: [] });
    const refreshed = nodes.find((n) => n.id === selected.key)?.data ?? null;
    if (refreshed) setSelected(refreshed);
  }, [state, selected?.key]);

  const onNodeClick = useCallback(
    (_e: React.MouseEvent, node: { data: GraphNodeData }) => {
      setSelected(node.data);
    },
    [],
  );

  return (
    <div className="rtw-root" data-testid="rtw-root">
      {state.status === 'error' && (
        <ErrorBanner error={state.error} legacyAdminUrl={legacyAdminUrl} />
      )}
      <RootCanvas
        state={state}
        onNodeClick={onNodeClick}
        saveLayoutUrl={buildSaveLayoutUrl(topologyUrl)}
        fetchImpl={fetchImpl ?? window.fetch}
        onSavedLayout={refresh}
      />
      {selected && (
        <Sidebar
          node={selected}
          onClose={() => setSelected(null)}
          promptMode="edit"
          onEditPrompt={(prompt) => setEditing({ node: selected, prompt })}
          onViewDefault={(prompt) =>
            setViewingDefault({ node: selected, prompt })
          }
          onEditModel={() => setEditingModel(selected)}
        />
      )}
      {editing && state.status === 'ready' && (
        <PromptEditModal
          prompt={editing.prompt}
          saveUrl={buildSavePromptUrl(
            topologyUrl,
            editing.node.key,
            _targetForPrompt(editing.prompt),
          )}
          fetchImpl={fetchImpl ?? window.fetch}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}
      {viewingDefault && state.status === 'ready' && (
        <DefaultPromptViewModal
          prompt={viewingDefault.prompt}
          saveUrl={buildSavePromptUrl(
            topologyUrl,
            viewingDefault.node.key,
            _targetForPrompt(viewingDefault.prompt),
          )}
          fetchImpl={fetchImpl ?? window.fetch}
          onClose={() => setViewingDefault(null)}
          onRestored={async () => {
            setViewingDefault(null);
            await refresh();
          }}
        />
      )}
      {editingModel && state.status === 'ready' && (
        <ModelEditModal
          nodeKey={editingModel.key}
          model={editingModel.model}
          availableModels={state.payload.available_models ?? []}
          saveUrl={buildSaveModelUrl(topologyUrl, editingModel.key)}
          fetchImpl={fetchImpl ?? window.fetch}
          onCancel={() => setEditingModel(null)}
          onSaved={async () => {
            setEditingModel(null);
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function _targetForPrompt(prompt: SidebarPrompt): PromptSaveTarget {
  return prompt.role === 'usage'
    ? { kind: 'usage_prompt' }
    : { kind: 'state_modifier', key: prompt.state_modifier_key ?? '0' };
}

interface RootCanvasProps {
  state: LoadState;
  onNodeClick: (e: React.MouseEvent, node: { data: GraphNodeData }) => void;
  saveLayoutUrl: string;
  fetchImpl: typeof fetch;
  onSavedLayout: () => void | Promise<void>;
  // Test seam — defaults to native window.confirm.
  confirmImpl?: (message: string) => boolean;
}

function RootCanvas({
  state,
  onNodeClick,
  saveLayoutUrl,
  fetchImpl,
  onSavedLayout,
  confirmImpl,
}: RootCanvasProps) {
  // ReactFlow-managed node/edge state — drives drag-and-drop in-session
  // and (after Save layout) persisted positions. Every fresh topology fetch
  // reseeds from `layoutTopology(...)`, which uses persisted positions when
  // available or falls back to dagre auto-layout.
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<GraphNodeData>([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState<GraphEdgeData>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const hasPersisted =
    state.status === 'ready' &&
    state.payload.nodes.some(
      (n) =>
        n.position &&
        typeof n.position.x === 'number' &&
        typeof n.position.y === 'number',
    );

  useEffect(() => {
    if (state.status !== 'ready') {
      setRfNodes([]);
      setRfEdges([]);
      setIsDirty(false);
      setSaveError(null);
      return;
    }
    const laid = layoutTopology(state.payload);
    setRfNodes(laid.nodes as GraphNode[]);
    setRfEdges(laid.edges as GraphEdge[]);
    setIsDirty(false);
    setSaveError(null);
  }, [state, setRfNodes, setRfEdges]);

  const handleSaveLayout = async () => {
    setSaving(true);
    setSaveError(null);
    const positions: Record<string, { x: number; y: number }> = {};
    for (const node of rfNodes) {
      positions[node.id] = { x: node.position.x, y: node.position.y };
    }
    const result = await saveTopologyLayout(
      saveLayoutUrl,
      positions,
      fetchImpl,
      document,
    );
    setSaving(false);
    if (result.ok) {
      setIsDirty(false);
      await onSavedLayout();
      return;
    }
    setSaveError(result.error.message);
  };

  const handleResetLayout = async () => {
    const confirmFn =
      confirmImpl ??
      (typeof window !== 'undefined' ? window.confirm.bind(window) : () => false);
    if (
      !confirmFn(
        'Reset to auto-layout? Saved positions will be discarded and the graph will recompute.',
      )
    ) {
      return;
    }
    setSaving(true);
    setSaveError(null);
    const result = await saveTopologyLayout(
      saveLayoutUrl,
      {},
      fetchImpl,
      document,
    );
    setSaving(false);
    if (result.ok) {
      setIsDirty(false);
      await onSavedLayout();
      return;
    }
    setSaveError(result.error.message);
  };

  if (state.status === 'ready' && state.payload.nodes.length === 0) {
    return (
      <div className="rtw-canvas">
        <div className="rtw-empty" data-testid="rtw-empty">
          no nodes to display
        </div>
      </div>
    );
  }

  return (
    <div className="rtw-canvas">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={() => setIsDirty(true)}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodeClick={onNodeClick}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
        {(isDirty || hasPersisted || saveError) && (
          <Panel position="top-right" className="rtw-layout-panel">
            {isDirty && (
              <button
                type="button"
                className="rtw-layout-panel__btn rtw-layout-panel__btn--primary"
                data-testid="rtw-save-layout"
                onClick={handleSaveLayout}
                disabled={saving}
              >
                {saving ? 'Saving…' : 'Save layout'}
              </button>
            )}
            {hasPersisted && (
              <button
                type="button"
                className="rtw-layout-panel__btn"
                data-testid="rtw-reset-layout"
                onClick={handleResetLayout}
                disabled={saving}
              >
                Reset to auto
              </button>
            )}
            {saveError && (
              <span
                className="rtw-layout-panel__error"
                data-testid="rtw-layout-error"
              >
                {saveError}
              </span>
            )}
          </Panel>
        )}
      </ReactFlow>
    </div>
  );
}

function ErrorBanner({
  error,
  legacyAdminUrl,
}: {
  error: TopologyError;
  legacyAdminUrl: string;
}) {
  return (
    <div className="rtw-banner" data-testid="rtw-error-banner" role="alert">
      <div className="rtw-banner__msg">{error.message}</div>
      <a className="rtw-banner__cta" href={legacyAdminUrl}>
        Edit prompts in the legacy admin
      </a>
    </div>
  );
}

function NodeGrip() {
  // 6-dot drag-handle icon. `aria-hidden` because drag is a pointer-only
  // interaction; keyboard users open the sidebar via the node click handler
  // bound elsewhere on the node body.
  return (
    <div className="rtw-node__grip" aria-hidden="true" title="Drag to reposition">
      <svg width="8" height="14" viewBox="0 0 8 14">
        <circle cx="2" cy="3" r="1.2" />
        <circle cx="6" cy="3" r="1.2" />
        <circle cx="2" cy="7" r="1.2" />
        <circle cx="6" cy="7" r="1.2" />
        <circle cx="2" cy="11" r="1.2" />
        <circle cx="6" cy="11" r="1.2" />
      </svg>
    </div>
  );
}

function OverrideBadge() {
  // Pencil icon — signals the node has at least one admin override on a prompt.
  return (
    <span
      className="rtw-node__override-badge"
      data-testid="rtw-node-override-badge"
      title="This node has admin overrides"
      aria-label="Overridden"
    >
      <svg width="11" height="11" viewBox="0 0 14 14" aria-hidden="true">
        <path
          d="M10.5 1.5 L12.5 3.5 L4.5 11.5 L2.0 12.0 L2.5 9.5 L10.5 1.5 Z"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    </span>
  );
}

function AgentNode({ data }: NodeProps<GraphNodeData>) {
  return (
    <div
      className={
        'rtw-node rtw-node--agent' +
        (data.has_override ? ' rtw-node--overridden' : '')
      }
    >
      <Handle type="target" position={Position.Top} />
      <div className="rtw-node__body">
        <div className="rtw-node__head">
          <div className="rtw-node__kind">Agent</div>
          {data.has_override && <OverrideBadge />}
        </div>
        <div className="rtw-node__title">{data.key}</div>
      </div>
      <NodeGrip />
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

function WorkerNode({ data }: NodeProps<GraphNodeData>) {
  return (
    <div
      className={
        'rtw-node rtw-node--worker' +
        (data.has_override ? ' rtw-node--overridden' : '')
      }
    >
      <Handle type="target" position={Position.Top} />
      <div className="rtw-node__body">
        <div className="rtw-node__head">
          <div className="rtw-node__kind">Worker</div>
          {data.has_override && <OverrideBadge />}
        </div>
        <div className="rtw-node__title">{data.key}</div>
      </div>
      <NodeGrip />
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const NODE_TYPES = { agent: AgentNode, worker: WorkerNode };

// All edges render as the same solid bezier. Layout spread (controlled in
// layout.ts via dagre's nodesep/ranksep) is what we tune to avoid skip-rank
// edges overlapping nodes — not the edge geometry. If a particular graph
// still has overlap after auto-layout, the user can drag nodes via the grip
// handle to clean it up.
function BezierEdge(props: EdgeProps<GraphEdgeData>) {
  const [path] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  });
  return <path id={props.id} className="react-flow__edge-path" d={path} />;
}

const EDGE_TYPES = { normal: BezierEdge, conditional: BezierEdge };

export async function fetchTopology(
  url: string,
  fetchImpl: typeof fetch = window.fetch,
): Promise<TopologyResponse | TopologyError> {
  try {
    const response = await fetchImpl(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      return { ...GENERIC_ERROR };
    }
    try {
      const body = (await response.json()) as TopologyResponse;
      return body;
    } catch {
      return { ...GENERIC_ERROR };
    }
  } catch {
    return { ...GENERIC_ERROR };
  }
}

function _isError(
  result: TopologyResponse | TopologyError,
): result is TopologyError {
  return (
    typeof result === 'object' &&
    result !== null &&
    'code' in result &&
    typeof (result as { code?: unknown }).code === 'string' &&
    !('nodes' in result)
  );
}
