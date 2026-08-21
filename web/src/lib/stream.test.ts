import { describe, expect, it } from 'vitest';
import { readMessages } from '@/lib/stream';

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const messages = [];
  for await (const message of readMessages(stream)) messages.push(message);
  return messages;
}

describe('reading the agent stream', () => {
  it('yields one message per event', async () => {
    const messages = await collect(
      streamOf('data: {"stage":"facts"}\n\ndata: {"stage":"deadline"}\n\n'),
    );
    expect(messages).toEqual([{ stage: 'facts' }, { stage: 'deadline' }]);
  });

  it('joins a message split across two network chunks', async () => {
    // A stage is one JSON object and the network does not respect that boundary. Half a deadline
    // parsed as a whole one would put a wrong date in front of a visitor.
    const messages = await collect(
      streamOf('data: {"stage":"dead', 'line","days_left":25}\n\n'),
    );
    expect(messages).toEqual([{ stage: 'deadline', days_left: 25 }]);
  });

  it('reads a final message that arrives without a trailing blank line', async () => {
    const messages = await collect(streamOf('data: {"stage":"done"}'));
    expect(messages).toEqual([{ stage: 'done' }]);
  });

  it('drops an unparseable event and keeps the ones after it', async () => {
    const messages = await collect(
      streamOf('data: {not json}\n\ndata: {"stage":"steps"}\n\n'),
    );
    expect(messages).toEqual([{ stage: 'steps' }]);
  });

  it('ignores lines that are not data', async () => {
    const messages = await collect(streamOf(': keep-alive\n\ndata: {"stage":"draft"}\n\n'));
    expect(messages).toEqual([{ stage: 'draft' }]);
  });
});
