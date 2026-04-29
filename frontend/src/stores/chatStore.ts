import { create } from 'zustand';
import api from '../api/client';
import { useSSE } from '../hooks/useSSE';
import type { Conversation, Message, SSEEvent } from '../types';

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  agentEvents: SSEEvent[];
  isStreaming: boolean;
  fetchConversations: () => Promise<void>;
  createConversation: (title: string, mode: 'normal' | 'agentic') => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
}

export const useChatStore = create<ChatState>()((set, get) => {
  const { stream, isStreaming } = useSSE();

  return {
    conversations: [],
    currentConversationId: null,
    messages: [],
    agentEvents: [],
    isStreaming,

    fetchConversations: async () => {
      try {
        const res = await api.get('/api/conversations');
        set({ conversations: res.data as Conversation[] });
      } catch (e) {
        console.error('Failed to fetch conversations:', e);
      }
    },

    createConversation: async (title: string, mode: 'normal' | 'agentic') => {
      try {
        const res = await api.post('/api/conversations', { title, mode });
        const conversation = res.data as Conversation;
        set((state) => ({
          conversations: [conversation, ...state.conversations],
        }));
        await get().selectConversation(conversation.id);
      } catch (e) {
        console.error('Failed to create conversation:', e);
      }
    },

    selectConversation: async (id: string) => {
      set({ currentConversationId: id, messages: [], agentEvents: [] });
      try {
        const res = await api.get(`/api/chat/conversations/${id}/messages`);
        set({ messages: res.data as Message[] });
      } catch (e) {
        console.error('Failed to fetch messages:', e);
      }
    },

    deleteConversation: async (id: string) => {
      try {
        await api.delete(`/api/conversations/${id}`);
        set((state) => {
          const filtered = state.conversations.filter((c) => c.id !== id);
          const newCurrentId =
            state.currentConversationId === id ? null : state.currentConversationId;
          const newMessages = newCurrentId === null ? [] : state.messages;
          return { conversations: filtered, currentConversationId: newCurrentId, messages: newMessages };
        });
      } catch (e) {
        console.error('Failed to delete conversation:', e);
      }
    },

    sendMessage: async (content: string) => {
      const { currentConversationId } = get();

      // Auto-create a conversation if none exists
      if (!currentConversationId) {
        await get().createConversation('New Conversation', 'normal');
      }

      const convId = get().currentConversationId;
      if (!convId) return;

      // Optimistically add user message
      const userMessage: Message = {
        id: `temp-${Date.now()}`,
        conversation_id: convId,
        role: 'user',
        content,
        tool_calls: null,
        tool_call_id: null,
        agent_steps: null,
        created_at: new Date().toISOString(),
      };
      set((state) => ({ messages: [...state.messages, userMessage] }));

      // Prepare assistant message placeholder
      let assistantContent = '';

      set({ isStreaming: true });

      await stream('http://localhost:8000/api/chat/send', { conversation_id: convId, content }, (event: SSEEvent) => {
        switch (event.event) {
          case 'text': {
            assistantContent += (event.data as { content: string }).content;
            set((state) => {
              const msgs = [...state.messages];
              const lastMsg = msgs[msgs.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                msgs[msgs.length - 1] = { ...lastMsg, content: assistantContent };
              } else {
                msgs.push({
                  id: `stream-${Date.now()}`,
                  conversation_id: convId,
                  role: 'assistant',
                  content: assistantContent,
                  tool_calls: null,
                  tool_call_id: null,
                  agent_steps: null,
                  created_at: new Date().toISOString(),
                });
              }
              return { messages: msgs };
            });
            break;
          }
          case 'thinking':
          case 'tool_call':
          case 'tool_result': {
            set((state) => ({ agentEvents: [...state.agentEvents, event] }));
            break;
          }
          case 'done': {
            set((state) => ({ agentEvents: [], isStreaming: false }));
            // Refresh conversations list to get updated timestamps
            get().fetchConversations();
            break;
          }
        }
      });

      set({ isStreaming: false });
    },
  };
});
