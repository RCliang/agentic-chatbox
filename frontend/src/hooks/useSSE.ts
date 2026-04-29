import { useState, useCallback, useRef } from 'react';
import type { SSEEvent } from '../types';

export function useSSE() {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const stream = useCallback(
    async (url: string, body: object, onEvent: (event: SSEEvent) => void) => {
      abortRef.current = new AbortController();
      setIsStreaming(true);
      try {
        const token = localStorage.getItem('token');
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
          signal: abortRef.current.signal,
        });

        if (!response.ok) {
          console.error('SSE request failed:', response.status, response.statusText);
          return;
        }

        if (!response.body) {
          console.error('Response body is null');
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split('\n\n');
          buffer = blocks.pop() || '';
          for (const block of blocks) {
            const eventMatch = block.match(/^event:\s*(.+)$/m);
            const dataMatch = block.match(/^data:\s*(.+)$/m);
            if (eventMatch && dataMatch) {
              try {
                onEvent({ event: eventMatch[1] as SSEEvent['event'], data: JSON.parse(dataMatch[1]) });
              } catch {
                console.error('Failed to parse SSE data:', dataMatch[1]);
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          console.error('SSE stream error:', e);
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { isStreaming, stream, abort };
}
