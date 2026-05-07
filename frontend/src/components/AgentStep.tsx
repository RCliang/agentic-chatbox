import { useState } from 'react';
import type { SSEEvent } from '../types';

interface AgentStepProps {
  event: SSEEvent;
}

export default function AgentStep({ event }: AgentStepProps) {
  const [expanded, setExpanded] = useState(false);

  switch (event.event) {
    case 'thinking': {
      const content = (event.data as { content: string }).content;
      return (
        <div className="mb-2 border-l-2 rounded-r-lg px-4 py-2" style={{ borderLeftColor: 'var(--accent-light)', background: 'var(--bg-surface)' }}>
          <p className="text-xs mb-1 font-medium" style={{ color: 'var(--accent-light)' }}>Thinking</p>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{content}</p>
        </div>
      );
    }

    case 'tool_call': {
      const data = event.data as { name: string; arguments: unknown };
      let argsStr = '';
      if (typeof data.arguments === 'string') {
        try {
          argsStr = JSON.stringify(JSON.parse(data.arguments), null, 2);
        } catch {
          argsStr = data.arguments;
        }
      } else {
        argsStr = JSON.stringify(data.arguments, null, 2);
      }
      return (
        <div className="mb-2 rounded-lg px-4 py-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
          <p className="text-xs mb-1 font-medium" style={{ color: 'var(--text-muted)' }}>Tool Call</p>
          <p className="text-sm font-mono" style={{ color: 'var(--success)' }}>
            {data.name}({argsStr.length > 200 ? argsStr.slice(0, 200) + '...' : argsStr})
          </p>
        </div>
      );
    }

    case 'tool_result': {
      const data = event.data as { name: string; result: string };
      const content = data.result;
      const isLong = content.length > 300;
      return (
        <div className="mb-2 rounded-lg px-4 py-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Tool Result</p>
            {isLong && (
              <span className="text-xs cursor-pointer" style={{ color: 'var(--accent-light)' }}>
                {expanded ? '收起' : '展开'}
              </span>
            )}
          </div>
          <pre className="text-sm whitespace-pre-wrap font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>
            {isLong && !expanded ? content.slice(0, 300) + '...' : content}
          </pre>
        </div>
      );
    }

    case 'node_enter':
    case 'node_exit':
    case 'plan':
    case 'plan_step_update':
    case 'interrupt':
      // These are handled by dedicated components (NodeTracker, PlanView, InterruptDialog)
      return null;

    default:
      return null;
  }
}
