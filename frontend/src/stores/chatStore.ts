import { create } from 'zustand';
import api from '../api/client';
import { createSSEStream } from '../hooks/useSSE';
import type { Conversation, KnowledgeBase, Message, Skill, SSEEvent, InterruptData, PlanStep, NodeStatus } from '../types';

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  agentEvents: SSEEvent[];
  isStreaming: boolean;
  skills: Skill[];
  knowledgeBases: KnowledgeBase[];
  fetchConversations: () => Promise<void>;
  createConversation: (title: string, mode: 'normal' | 'agentic') => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  updateConversationMode: (id: string, mode: 'normal' | 'agentic') => Promise<void>;
  updateConversationSkill: (id: string, skillId: string | null) => Promise<void>;
  updateConversationKB: (id: string, kbId: string | null) => Promise<void>;
  updateConversationTools: (id: string, tools: string[]) => Promise<void>;
  fetchSkills: () => Promise<void>;
  seedSkills: () => Promise<void>;
  fetchKnowledgeBases: () => Promise<void>;
  interruptData: InterruptData | null;
  planSteps: PlanStep[];
  activeNodes: NodeStatus[];
  resumeInterrupt: (action: string, payload?: Record<string, unknown>) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
}

export const useChatStore = create<ChatState>()((set, get) => {
  const sse = createSSEStream();

  return {
    conversations: [],
    currentConversationId: null,
    messages: [],
    agentEvents: [],
    isStreaming: false,
    skills: [],
    knowledgeBases: [],
    interruptData: null,
    planSteps: [],
    activeNodes: [],

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

    updateConversationMode: async (id: string, mode: 'normal' | 'agentic') => {
      try {
        await api.patch(`/api/conversations/${id}`, { mode });
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, mode } : c,
          ),
        }));
      } catch (e) {
        console.error('Failed to update conversation mode:', e);
      }
    },

    updateConversationSkill: async (id: string, skillId: string | null) => {
      try {
        await api.patch(`/api/conversations/${id}`, { skill_id: skillId || '' });
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, skill_id: skillId } : c,
          ),
        }));
      } catch (e) {
        console.error('Failed to update conversation skill:', e);
      }
    },

    fetchSkills: async () => {
      try {
        const res = await api.get('/api/skills');
        set({ skills: res.data as Skill[] });
      } catch (e) {
        console.error('Failed to fetch skills:', e);
      }
    },

    seedSkills: async () => {
      try {
        await api.post('/api/skills/seed');
        await get().fetchSkills();
      } catch (e) {
        console.error('Failed to seed skills:', e);
      }
    },

    fetchKnowledgeBases: async () => {
      try {
        const res = await api.get('/api/knowledge/bases');
        set({ knowledgeBases: res.data as KnowledgeBase[] });
      } catch (e) {
        console.error('Failed to fetch knowledge bases:', e);
      }
    },

    updateConversationKB: async (id: string, kbId: string | null) => {
      try {
        await api.patch(`/api/conversations/${id}`, { knowledge_base_id: kbId || '' });
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, knowledge_base_id: kbId } : c,
          ),
        }));
      } catch (e) {
        console.error('Failed to update conversation KB:', e);
      }
    },

    updateConversationTools: async (id: string, tools: string[]) => {
      try {
        await api.patch(`/api/conversations/${id}`, { enabled_tools: tools });
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, enabled_tools: tools.length > 0 ? tools : null } : c,
          ),
        }));
      } catch (e) {
        console.error('Failed to update conversation tools:', e);
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

      // Update conversation title to first user message (truncated)
      const conv = get().conversations.find((c) => c.id === convId);
      if (conv && conv.title === 'New Conversation') {
        const truncated = content.length > 20 ? content.slice(0, 20) + '...' : content;
        try {
          await api.patch(`/api/conversations/${convId}`, { title: truncated });
          set((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === convId ? { ...c, title: truncated } : c,
            ),
          }));
        } catch (e) {
          console.error('Failed to update conversation title:', e);
        }
      }

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

      await sse.stream('http://localhost:8000/api/chat/send', { conversation_id: convId, content }, (event: SSEEvent) => {
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
          case 'node_enter': {
            const d = event.data as { node: string; label: string };
            set((state) => ({
              activeNodes: [...state.activeNodes, { node: d.node, label: d.label, status: 'running' as const }],
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'node_exit': {
            const d = event.data as { node: string; duration_ms: number };
            set((state) => ({
              activeNodes: state.activeNodes.map((n) =>
                n.node === d.node ? { ...n, status: 'done' as const, duration_ms: d.duration_ms } : n
              ),
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'plan': {
            const d = event.data as { steps: PlanStep[] };
            set((state) => ({
              planSteps: d.steps,
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'plan_step_update': {
            const d = event.data as { step_id: string; status: string };
            set((state) => ({
              planSteps: state.planSteps.map((s) =>
                s.id === d.step_id ? { ...s, status: d.status as PlanStep['status'] } : s
              ),
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'interrupt': {
            const d = event.data as InterruptData;
            set({ interruptData: d, isStreaming: false });
            break;
          }
          case 'done': {
            set({ agentEvents: [], isStreaming: false, activeNodes: [], planSteps: [], interruptData: null });
            get().fetchConversations();
            break;
          }
        }
      });

      set({ isStreaming: false });
    },

    resumeInterrupt: async (action: string, payload: Record<string, unknown> = {}) => {
      const convId = get().currentConversationId;
      if (!convId) return;

      set({ isStreaming: true, interruptData: null });

      let assistantContent = '';

      await sse.stream('http://localhost:8000/api/chat/resume', {
        conversation_id: convId,
        action,
        payload,
      }, (event: SSEEvent) => {
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
          case 'tool_result':
          case 'node_enter':
          case 'node_exit':
          case 'plan':
          case 'plan_step_update': {
            set((state) => ({ agentEvents: [...state.agentEvents, event] }));
            break;
          }
          case 'interrupt': {
            const d = event.data as InterruptData;
            set({ interruptData: d, isStreaming: false });
            break;
          }
          case 'done': {
            set({ agentEvents: [], isStreaming: false, activeNodes: [], planSteps: [], interruptData: null });
            get().fetchConversations();
            break;
          }
        }
      });

      set({ isStreaming: false });
    },
  };
});
