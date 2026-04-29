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
            ? 'bg-[#16213e] rounded-2xl rounded-br-sm'
            : 'bg-[#16213e] rounded-lg'
        }`}
      >
        {!isUser && (
          <p className="text-xs text-blue-400 mb-1 font-medium">Assistant</p>
        )}
        <div className="text-gray-200 text-sm leading-relaxed prose prose-invert prose-sm max-w-none">
          {message.content ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : (
            <span className="text-gray-500 italic">No content</span>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
