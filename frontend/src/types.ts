export interface NodeStatus {
  node: string;
  label: string;
  status: 'running' | 'done';
  duration_ms?: number;
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
    [key: string]: unknown;
  };
}
