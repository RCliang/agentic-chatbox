import { useState } from 'react';
import type { SSEEvent } from '../types';

interface AgentStepProps {
  event: SSEEvent;
}

export default function AgentStep({ event }: AgentStepProps) {
  const [expanded, setExpanded] = useState(false);

  switch (event.event) {
    case 'thinking': {
      const content = (event.data as { content: string }).content;
      return (
        <div className="mb-2 bg-[#1a1a2e] border-l-2 border-red-500 rounded-r-lg px-4 py-2">
          <p className="text-xs text-gray-400 mb-1">Thinking</p>
          <p className="text-sm text-gray-300">{content}</p>
        </div>
      );
    }

    case 'tool_call': {
      const data = event.data as { name: string; arguments: string };
      let argsStr = '';
      try {
        argsStr = JSON.stringify(JSON.parse(data.arguments), null, 2);
      } catch {
        argsStr = data.arguments;
      }
      return (
        <div className="mb-2 bg-[#1a2a1a] border border-[#2d4a22] rounded-lg px-4 py-2">
          <p className="text-xs text-gray-400 mb-1">Tool Call</p>
          <p className="text-sm text-green-400 font-mono">
            {data.name}({argsStr.length > 200 ? argsStr.slice(0, 200) + '...' : argsStr})
          </p>
        </div>
      );
    }

    case 'tool_result': {
      const content = (event.data as { content: string }).content;
      const isLong = content.length > 300;
      return (
        <div className="mb-2 bg-[#1a1a2a] border border-[#333] rounded-lg px-4 py-2">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            <p className="text-xs text-gray-400">Tool Result</p>
            {isLong && (
              <span className="text-xs text-gray-500">
                {expanded ? '收起' : '展开'}
              </span>
            )}
          </div>
          <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono mt-1">
            {isLong && !expanded ? content.slice(0, 300) + '...' : content}
          </pre>
        </div>
      );
    }

    default:
      return null;
  }
}
