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
  event: 'text' | 'thinking' | 'tool_call' | 'tool_result' | 'done'
    | 'node_enter' | 'node_exit' | 'plan' | 'plan_step_update' | 'interrupt';
  data: unknown;
}

export interface PlanStep {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'done' | 'failed';
}

export interface InterruptData {
  type: 'plan' | 'tool';
  payload: {
    steps?: PlanStep[];
    tool_name?: string;
    arguments?: Record<string, unknown>;
    call_id?: string;
  };
}

export interface NodeStatus {
  node: string;
  label: string;
  status: 'running' | 'done';
  duration_ms?: number;
}

export interface SkillToolItem {
  name: string;
  when: string;
  required: boolean;
}

export interface SkillRefItem {
  type: 'knowledge_base' | 'text' | 'url';
  source: string;
  title: string;
  inject: 'always' | 'on_demand' | 'on_step';
  match_tools?: string[];
}

export interface SkillExampleItem {
  user: string;
  assistant: string;
}

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  instructions: string;
  tools: SkillToolItem[] | null;
  references: SkillRefItem[] | null;
  examples: SkillExampleItem[] | null;
  knowledge_base_id: string | null;
  is_builtin: boolean;
  planning_mode: 'auto' | 'always' | 'never';
  confirm_plan: boolean;
  confirm_tools: string[] | null;
  created_at: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
}
