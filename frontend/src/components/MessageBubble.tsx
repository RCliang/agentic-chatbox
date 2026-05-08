import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../types';

interface AgentStepsData {
  events?: { event: string; data: unknown }[];
  plan?: { id: string; title: string; status: string }[];
  nodes?: { node: string; label: string; status: string; duration_ms?: number }[];
}

interface MessageBubbleProps {
  message: Message;
}

function AgentProcessView({ steps }: { steps: AgentStepsData }) {
  const [expanded, setExpanded] = useState(false);
  const events = steps.events || [];
  const thinkingEvents = events.filter((e) => e.event === 'thinking');
  const toolEvents = events.filter((e) => e.event === 'tool_call' || e.event === 'tool_result');
  const plan = steps.plan;
  const nodes = steps.nodes;

  const hasContent = thinkingEvents.length > 0 || toolEvents.length > 0 || (plan && plan.length > 0) || (nodes && nodes.length > 0);
  if (!hasContent) return null;

  return (
    <div className="mt-2 rounded-lg overflow-hidden" style={{ border: '1px solid var(--border-light)' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium cursor-pointer transition-colors"
        style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)' }}
      >
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
          fill="currentColor" viewBox="0 0 20 20"
        >
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>
        思考过程
        <span style={{ color: 'var(--text-muted)' }}>
          ({nodes && nodes.length > 0 ? `${nodes.length} 节点` : ''}
          {thinkingEvents.length > 0 ? `${nodes && nodes.length > 0 ? ', ' : ''}${thinkingEvents.length} 思考` : ''}
          {toolEvents.filter((e) => e.event === 'tool_call').length > 0 ? `, ${toolEvents.filter((e) => e.event === 'tool_call').length} 工具调用` : ''}
          {plan && plan.length > 0 ? `, ${plan.length} 步计划` : ''})
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 space-y-2" style={{ background: 'var(--bg-primary)' }}>
          {/* Nodes flow */}
          {nodes && nodes.length > 0 && (
            <div className="flex items-center gap-1 flex-wrap mb-2">
              {nodes.map((n, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium"
                  style={{
                    background: n.status === 'done' ? 'var(--success-muted)' : 'var(--accent-surface)',
                    color: n.status === 'done' ? 'var(--success)' : 'var(--accent-light)',
                  }}
                >
                  {n.status === 'done' ? '✓' : '●'} {n.label}
                  {n.duration_ms != null && <span style={{ color: 'var(--text-muted)' }}>{n.duration_ms}ms</span>}
                </span>
              ))}
            </div>
          )}

          {/* Plan */}
          {plan && plan.length > 0 && (
            <div className="rounded p-2" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)' }}>
              <p className="text-[10px] font-medium mb-1" style={{ color: 'var(--text-muted)' }}>执行计划</p>
              {plan.map((s) => (
                <div key={s.id} className="flex items-center gap-1.5 text-xs py-0.5">
                  <span>{s.status === 'done' ? '✅' : s.status === 'running' ? '🔄' : s.status === 'failed' ? '❌' : '⬜'}</span>
                  <span style={{ color: 'var(--text-primary)' }}>{s.title}</span>
                </div>
              ))}
            </div>
          )}

          {/* Events */}
          {events.filter((e) => e.event === 'thinking' || e.event === 'tool_call' || e.event === 'tool_result').map((evt, i) => {
            const d = evt.data as Record<string, unknown>;
            if (evt.event === 'thinking') {
              return (
                <div key={i} className="rounded p-2 text-xs" style={{ background: 'var(--bg-card)', color: 'var(--text-secondary)', borderLeft: '2px solid var(--accent)' }}>
                  <span className="text-[10px] font-medium" style={{ color: 'var(--accent-light)' }}>思考</span>
                  <p className="mt-0.5 whitespace-pre-wrap">{d.content as string}</p>
                </div>
              );
            }
            if (evt.event === 'tool_call') {
              return (
                <div key={i} className="rounded p-2 text-xs" style={{ background: 'var(--bg-card)', borderLeft: '2px solid var(--warning, #f59e0b)' }}>
                  <span className="text-[10px] font-medium" style={{ color: 'var(--warning, #f59e0b)' }}>工具调用: {d.name as string}</span>
                  <pre className="mt-0.5 overflow-x-auto text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    {JSON.stringify(d.arguments, null, 2)}
                  </pre>
                </div>
              );
            }
            if (evt.event === 'tool_result') {
              const result = d.result as string;
              const truncated = result && result.length > 300 ? result.slice(0, 300) + '...' : result;
              return (
                <div key={i} className="rounded p-2 text-xs" style={{ background: 'var(--bg-card)', borderLeft: '2px solid var(--success)' }}>
                  <span className="text-[10px] font-medium" style={{ color: 'var(--success)' }}>工具结果: {d.name as string}</span>
                  <pre className="mt-0.5 overflow-x-auto text-[11px] whitespace-pre-wrap" style={{ color: 'var(--text-muted)' }}>
                    {truncated}
                  </pre>
                </div>
              );
            }
            return null;
          })}
        </div>
      )}
    </div>
  );
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const agentSteps = message.agent_steps as AgentStepsData | null;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] px-4 py-3 ${
          isUser
            ? 'rounded-2xl rounded-br-sm'
            : 'rounded-2xl rounded-bl-sm'
        }`}
        style={{
          background: isUser ? 'var(--accent)' : 'var(--bg-card)',
          color: isUser ? '#ffffff' : 'var(--text-primary)',
          border: isUser ? undefined : '1px solid var(--border-color)',
        }}
      >
        {!isUser && (
          <p className="text-xs mb-1 font-medium" style={{ color: 'var(--accent-light)' }}>Assistant</p>
        )}
        <div className="text-sm leading-relaxed prose prose-sm max-w-none" style={{ color: isUser ? '#ffffff' : 'var(--text-primary)' }}>
          {message.content ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : (
            <span className="italic" style={{ color: isUser ? 'rgba(255,255,255,0.7)' : 'var(--text-muted)' }}>No content</span>
          )}
        </div>
        {/* Agent process details (persisted) */}
        {!isUser && agentSteps && (agentSteps as AgentStepsData).events && (
          <AgentProcessView steps={agentSteps as AgentStepsData} />
        )}
        <p className="text-xs mt-1" style={{ color: isUser ? 'rgba(255,255,255,0.6)' : 'var(--text-muted)' }}>
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
