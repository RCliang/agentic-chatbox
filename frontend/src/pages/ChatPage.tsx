import { useEffect } from 'react';
import { useChatStore } from '../stores/chatStore';
import Sidebar from '../components/Sidebar';
import ChatArea from '../components/ChatArea';

export default function ChatPage() {
  const fetchConversations = useChatStore((s) => s.fetchConversations);
  const createConversation = useChatStore((s) => s.createConversation);
  const seedSkills = useChatStore((s) => s.seedSkills);
  const fetchSkills = useChatStore((s) => s.fetchSkills);
  const fetchKnowledgeBases = useChatStore((s) => s.fetchKnowledgeBases);

  useEffect(() => {
    fetchConversations().then(() => {
      // If no conversations exist, create one
      const current = useChatStore.getState().conversations;
      if (current.length === 0) {
        createConversation('New Conversation', 'normal');
      }
    });
    // Seed builtin skills then fetch all
    seedSkills().then(() => fetchSkills());
    fetchKnowledgeBases();
  }, [fetchConversations, createConversation, seedSkills, fetchSkills, fetchKnowledgeBases]);

  return (
    <div className="flex h-screen" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      <Sidebar />
      <ChatArea />
    </div>
  );
}
