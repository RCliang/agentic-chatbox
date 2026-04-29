import { useEffect } from 'react';
import { useChatStore } from '../stores/chatStore';
import Sidebar from '../components/Sidebar';
import ChatArea from '../components/ChatArea';

export default function ChatPage() {
  const fetchConversations = useChatStore((s) => s.fetchConversations);
  const createConversation = useChatStore((s) => s.createConversation);

  useEffect(() => {
    fetchConversations().then(() => {
      // If no conversations exist, create one
      const current = useChatStore.getState().conversations;
      if (current.length === 0) {
        createConversation('New Conversation', 'normal');
      }
    });
  }, [fetchConversations, createConversation]);

  return (
    <div className="flex h-screen bg-[#0d0d1a] text-gray-200">
      <Sidebar />
      <ChatArea />
    </div>
  );
}
