import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import type { Conversation } from '../types';

export default function Sidebar() {
  const navigate = useNavigate();

  const conversations = useChatStore((s) => s.conversations);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const selectConversation = useChatStore((s) => s.selectConversation);
  const createConversation = useChatStore((s) => s.createConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);

  const sortedConversations = [...conversations].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <div className="w-64 shrink-0 flex flex-col h-full" style={{ background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)' }}>
      {/* Logo */}
      <div className="p-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <div className="flex items-center gap-2">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <h1 className="text-base font-semibold tracking-tight" style={{ color: 'var(--text-heading)' }}>Agentic Chatbox</h1>
        </div>
      </div>

      {/* New conversation */}
      <div className="p-3">
        <button
          onClick={() => createConversation('New Conversation', 'normal')}
          className="w-full py-2 px-4 rounded-lg transition-colors text-sm font-medium cursor-pointer"
          style={{ background: 'var(--accent-surface)', color: 'var(--accent-light)', border: '1px solid var(--accent-muted)' }}
        >
          + 新建对话
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2">
        {sortedConversations.length === 0 && (
          <p className="text-sm text-center mt-8" style={{ color: 'var(--text-muted)' }}>暂无对话</p>
        )}
        {sortedConversations.map((conv: Conversation) => (
          <div
            key={conv.id}
            className={`group flex items-center justify-between px-3 py-2.5 my-0.5 rounded-lg cursor-pointer transition-colors border-l-2 ${
              currentConversationId === conv.id
                ? ''
                : 'border-transparent'
            }`}
            style={{
              background: currentConversationId === conv.id ? 'var(--bg-card)' : undefined,
              borderLeftColor: currentConversationId === conv.id ? 'var(--accent)' : undefined,
            }}
            onClick={() => selectConversation(conv.id)}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{conv.title}</p>
              <span
                className="text-xs px-1.5 py-0.5 rounded mt-1 inline-block"
                style={
                  conv.mode === 'agentic'
                    ? { background: 'var(--accent-muted)', color: 'var(--accent-light)' }
                    : { background: 'var(--bg-surface)', color: 'var(--text-muted)' }
                }
              >
                {conv.mode === 'agentic' ? 'Agentic' : 'Normal'}
              </span>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteConversation(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 transition-opacity ml-2 text-xs cursor-pointer"
              style={{ color: 'var(--text-muted)' }}
              onMouseEnter={(e) => e.currentTarget.style.color = 'var(--danger)'}
              onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
              title="删除对话"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {/* Management section */}
      <div className="px-3 py-2 space-y-1" style={{ borderTop: '1px solid var(--border-color)' }}>
        <button
          onClick={() => navigate('/admin/knowledge')}
          className="w-full py-2 px-4 rounded-lg transition-colors text-sm text-left flex items-center gap-2 cursor-pointer"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-card)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
          </svg>
          知识库管理
        </button>

        <button
          onClick={() => navigate('/admin/skills')}
          className="w-full py-2 px-4 rounded-lg transition-colors text-sm text-left flex items-center gap-2 cursor-pointer"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-card)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
          </svg>
          Skills 管理
        </button>
      </div>
    </div>
  );
}
