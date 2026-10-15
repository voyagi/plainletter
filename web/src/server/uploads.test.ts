// @vitest-environment node
// The settings are read on the server, and the schema refuses a server value read in a browser.
import { afterEach, describe, expect, it, vi } from 'vitest';

// The real settings module, read fresh from a stubbed environment each time. The default is the
// property worth pinning: a deployment that forgot this setting must come up closed.
async function uploadsWith(value: string): Promise<boolean> {
  vi.stubEnv('PLAINLETTER_STAFFED_DESK', value);
  vi.resetModules();
  const { uploadsOpen } = await import('./uploads');
  return uploadsOpen();
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('whether this desk takes a letter', () => {
  it('stays closed when the setting is left out', async () => {
    // An empty value is how an unset variable arrives here: the schema reads it as absent.
    expect(await uploadsWith('')).toBe(false);
  });

  it('stays closed when it is set to false', async () => {
    expect(await uploadsWith('false')).toBe(false);
  });

  it('opens only for an explicit true', async () => {
    expect(await uploadsWith('true')).toBe(true);
  });

  it('refuses to start on anything else, rather than guessing which way was meant', async () => {
    await expect(uploadsWith('yes')).rejects.toThrow(/Invalid environment variables/);
  });
});
