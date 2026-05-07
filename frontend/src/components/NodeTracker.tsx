import type { NodeStatus } from '../types';

interface NodeTrackerProps {
  nodes: NodeStatus[];
}

export default function NodeTracker({ nodes }: NodeTrackerProps) {
  if (nodes.length === 0) return null;

  return (
    <div className="flex items-center gap-2 mb-3 px-4 py-2 rounded-lg text-xs"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
      {nodes.map((node, i) => (
        <div key={node.node + i} className="flex items-center gap-1">
          {i > 0 && <span style={{ color: 'var(--text-muted)' }}>→</span>}
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${
            node.status === 'running' ? 'animate-pulse' : ''
          }`} style={{
            background: node.status === 'done' ? 'var(--success)' : 'var(--accent)',
            color: '#fff',
          }}>
            {node.status === 'done' ? '✓' : '●'} {node.label}
            {node.duration_ms !== undefined && (
              <span className="opacity-70">{(node.duration_ms / 1000).toFixed(1)}s</span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
