import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Without this the rendered trees pile up in one document and a `getByText` that should find one
// element finds four, which reads as a component bug rather than as a test-harness one.
afterEach(cleanup);
