import type { SSEEvent } from '../types';

export function createSSEStream() {
  let abortController: AbortController | null = null;

  async function stream(url: string, body: object, onEvent: (event: SSEEvent) => void) {
    abortController = new AbortController();
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: abortController.signal,
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
      abortController = null;
    }
  }

  function abort() {
    abortController?.abort();
    abortController = null;
  }

  return { stream, abort };
}
