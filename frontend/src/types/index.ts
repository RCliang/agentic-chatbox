export interface User {
  id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
  department_id: string | null;
  position: string | null;
  is_dept_admin: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  mode: 'normal' | 'agentic';
  skill_id: string | null;
  knowledge_base_id: string | null;
  enabled_tools: string[] | null;
  created_at: string;
  updated_at: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string | null;
  tool_calls: unknown | null;
  tool_call_id: string | null;
  agent_steps: unknown | null;
  created_at: string;
}

export interface SSEEvent {
  event: 'text' | 'thinking' | 'tool_call' | 'tool_result' | 'done';
  data: unknown;
}
