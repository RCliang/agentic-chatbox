import { useState } from 'react';
import type { InterruptData, PlanStep } from '../types';

interface InterruptDialogProps {
  data: InterruptData;
  onAction: (action: 'approve' | 'reject' | 'edit', payload?: Record<string, unknown>) => void;
}

export default function InterruptDialog({ data, onAction }: InterruptDialogProps) {
  const [editedSteps, setEditedSteps] = useState<PlanStep[] | null>(null);

  if (data.type === 'plan') {
    const steps = editedSteps || data.payload.steps || [];
    return (
      <div className="mb-4 rounded-lg p-4" style={{
        background: 'var(--bg-surface)',
        border: '2px solid var(--accent)',
      }}>
        <p className="text-sm font-medium mb-3" style={{ color: 'var(--accent-light)' }}>
          Plan Confirmation
        </p>
        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          Review the plan below. You can approve, reject, or edit steps.
        </p>
        <div className="mb-3 space-y-2">
          {steps.map((step, i) => (
            <div key={step.id} className="flex items-start gap-2 p-2 rounded"
              style={{ background: 'var(--bg-primary)' }}>
              <span className="text-xs mt-1 font-mono" style={{ color: 'var(--text-muted)' }}>
                {i + 1}.
              </span>
              <div className="flex-1">
                <input
                  className="w-full text-sm bg-transparent border-none outline-none"
                  style={{ color: 'var(--text-primary)' }}
                  value={step.title}
                  onChange={(e) => {
                    const newSteps = [...steps];
                    newSteps[i] = { ...step, title: e.target.value };
                    setEditedSteps(newSteps);
                  }}
                />
                <input
                  className="w-full text-xs bg-transparent border-none outline-none mt-1"
                  style={{ color: 'var(--text-secondary)' }}
                  value={step.description}
                  onChange={(e) => {
                    const newSteps = [...steps];
                    newSteps[i] = { ...step, description: e.target.value };
                    setEditedSteps(newSteps);
                  }}
                />
              </div>
              <button
                className="text-xs px-1 hover:opacity-70"
                style={{ color: 'var(--error)' }}
                onClick={() => {
                  const newSteps = steps.filter((_, j) => j !== i);
                  setEditedSteps(newSteps);
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            className="px-3 py-1.5 rounded-lg text-sm text-white"
            style={{ background: 'var(--success)' }}
            onClick={() => {
              if (editedSteps) {
                onAction('edit', { steps: editedSteps });
              } else {
                onAction('approve');
              }
            }}
          >
            {editedSteps ? 'Approve Edited Plan' : 'Approve'}
          </button>
          <button
            className="px-3 py-1.5 rounded-lg text-sm"
            style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}
            onClick={() => onAction('reject')}
          >
            Reject
          </button>
        </div>
      </div>
    );
  }

  // Tool confirmation
  return (
    <div className="mb-4 rounded-lg p-4" style={{
      background: 'var(--bg-surface)',
      border: '2px solid var(--accent)',
    }}>
      <p className="text-sm font-medium mb-2" style={{ color: 'var(--accent-light)' }}>
        Tool Confirmation
      </p>
      <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
        The agent wants to use the following tool. Approve or reject?
      </p>
      <div className="p-2 rounded mb-3 font-mono text-sm" style={{ background: 'var(--bg-primary)', color: 'var(--success)' }}>
        {data.payload.tool_name}({JSON.stringify(data.payload.arguments, null, 2)})
      </div>
      <div className="flex gap-2">
        <button
          className="px-3 py-1.5 rounded-lg text-sm text-white"
          style={{ background: 'var(--success)' }}
          onClick={() => onAction('approve')}
        >
          Approve
        </button>
        <button
          className="px-3 py-1.5 rounded-lg text-sm"
          style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}
          onClick={() => onAction('reject')}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
