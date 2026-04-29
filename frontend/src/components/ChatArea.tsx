import { useState, useRef, useEffect, FormEvent } from 'react';
import { useChatStore } from '../stores/chatStore';
import MessageBubble from './MessageBubble';
import AgentStep from './AgentStep';

export default function ChatArea() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = useChatStore((s) => s.messages);
  const agentEvents = useChatStore((s) => s.agentEvents);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const conversations = useChatStore((s) => s.conversations);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const sendMessage = useChatStore((s) => s.sendMessage);

  const currentConversation = conversations.find((c) => c.id === currentConversationId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentEvents]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput('');
    sendMessage(trimmed);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0d0d1a]">
      {/* Top bar */}
      <div className="shrink-0 px-6 py-3 border-b border-[#1a1a2e] flex items-center gap-3">
        {currentConversation && (
          <>
            <span
              className={`text-xs px-2 py-0.5 rounded font-medium ${
                currentConversation.mode === 'agentic'
                  ? 'bg-red-500/20 text-red-400'
                  : 'bg-blue-500/20 text-blue-400'
              }`}
            >
              {currentConversation.mode === 'agentic' ? 'Agentic' : 'Normal'}
            </span>
            <span className="text-sm text-gray-200">{currentConversation.title}</span>
          </>
        )}
        {!currentConversation && (
          <span className="text-sm text-gray-400">Select or create a conversation</span>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && agentEvents.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500 text-sm">Send a message to start the conversation</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Agent events display */}
        {agentEvents.map((evt, idx) => (
          <AgentStep key={`agent-${idx}`} event={evt} />
        ))}

        {isStreaming && (
          <div className="flex justify-start mb-4">
            <div className="bg-[#16213e] rounded-lg px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 px-6 py-4 border-t border-[#1a1a2e]">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            disabled={isStreaming}
            className="flex-1 bg-[#16213e] border border-[#333] rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 transition-colors"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
