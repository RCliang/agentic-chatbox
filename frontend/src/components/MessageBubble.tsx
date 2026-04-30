import ReactMarkdown from 'react-markdown';
import type { Message } from '../types';

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

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
        <p className="text-xs mt-1" style={{ color: isUser ? 'rgba(255,255,255,0.6)' : 'var(--text-muted)' }}>
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
