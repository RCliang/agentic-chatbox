import { useState } from 'react';
import type { PlanStep } from '../types';

interface PlanViewProps {
  steps: PlanStep[];
}

const STATUS_ICONS: Record<PlanStep['status'], string> = {
  pending: '○',
  running: '🔄',
  done: '✅',
  failed: '❌',
};

export default function PlanView({ steps }: PlanViewProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-3 rounded-lg overflow-hidden"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
      <div
        className="flex items-center justify-between px-4 py-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs font-medium" style={{ color: 'var(--accent-light)' }}>
          Plan ({steps.filter(s => s.status === 'done').length}/{steps.length})
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {expanded ? '收起' : '展开'}
        </span>
      </div>
      {expanded && (
        <div className="px-4 pb-3">
          {steps.map((step, i) => (
            <div key={step.id} className="flex items-start gap-2 py-1">
              <span className="text-sm mt-0.5">{STATUS_ICONS[step.status]}</span>
              <div className="flex-1 min-w-0">
                <p className={`text-sm ${step.status === 'running' ? 'font-medium' : ''}`}
                  style={{ color: step.status === 'done' ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                  {i + 1}. {step.title}
                </p>
                {step.description && step.status === 'running' && (
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                    {step.description}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
