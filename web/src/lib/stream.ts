import type { AgentMessage } from '@/lib/reading';

// The runtime writes one JSON object per `data:` line and separates messages with a blank line.
// Reading it by hand rather than with EventSource is not a preference: the console sends a letter,
// which means a POST with a body, and EventSource can only issue a GET.

const DATA = 'data: ';

export async function* readMessages(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<AgentMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let split = buffer.indexOf('\n\n');
      while (split !== -1) {
        const message = parse(buffer.slice(0, split));
        if (message) yield message;
        buffer = buffer.slice(split + 2);
        split = buffer.indexOf('\n\n');
      }
    }
    const last = parse(buffer);
    if (last) yield last;
  } finally {
    reader.releaseLock();
  }
}

function parse(block: string): AgentMessage | null {
  const payload = block
    .split('\n')
    .filter((line) => line.startsWith(DATA))
    .map((line) => line.slice(DATA.length))
    .join('');
  if (!payload) return null;
  try {
    return JSON.parse(payload) as AgentMessage;
  } catch {
    // A half-written message is not an error the volunteer can do anything about, and the stages
    // that follow will still arrive. Dropping it beats tearing the reading down.
    return null;
  }
}
