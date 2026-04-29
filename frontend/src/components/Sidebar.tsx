import { useChatStore } from '../stores/chatStore';
import type { Conversation } from '../types';

export default function Sidebar() {
  const conversations = useChatStore((s) => s.conversations);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const selectConversation = useChatStore((s) => s.selectConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);

  const handleNewConversation = () => {
    createConversation('New Conversation', 'normal');
  };

  const sortedConversations = [...conversations].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <div className="w-64 shrink-0 bg-[#0f0f1a] border-r border-[#1a1a2e] flex flex-col h-full">
      <div className="p-4">
        <button
          onClick={handleNewConversation}
          className="w-full py-2 px-4 bg-[#16213e] text-blue-400 rounded-lg hover:bg-[#1a2a4e] transition-colors text-sm font-medium"
        >
          + 新建对话
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2">
        {sortedConversations.length === 0 && (
          <p className="text-gray-500 text-sm text-center mt-8">暂无对话</p>
        )}
        {sortedConversations.map((conv: Conversation) => (
          <div
            key={conv.id}
            className={`group flex items-center justify-between px-3 py-2.5 my-0.5 rounded-lg cursor-pointer transition-colors ${
              currentConversationId === conv.id
                ? 'bg-[#16213e] border-l-2 border-blue-400'
                : 'hover:bg-[#1a1a2e] border-l-2 border-transparent'
            }`}
            onClick={() => selectConversation(conv.id)}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-200 truncate">{conv.title}</p>
              <span
                className={`text-xs px-1.5 py-0.5 rounded mt-1 inline-block ${
                  conv.mode === 'agentic'
                    ? 'bg-red-500/20 text-red-400'
                    : 'bg-blue-500/20 text-blue-400'
                }`}
              >
                {conv.mode === 'agentic' ? 'Agentic' : 'Normal'}
              </span>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteConversation(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity ml-2 text-xs"
              title="删除对话"
            >
              x
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
