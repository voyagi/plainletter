// Architecture boundaries for the console. The rule file is the documented architecture: the
// browser must never reach the modules that hold cloud credentials, and nothing may cycle.
const fs = require('node:fs');
const path = require('node:path');

module.exports = {
  forbidden: [
    {
      name: 'no-client-to-server',
      severity: 'error',
      comment:
        'Client components must not import server-only modules. Those modules sign requests to the agent runtime, so an import would pull credentials into the browser bundle.',
      from: { path: '^src/components' },
      to: { path: '^src/server' },
    },
    {
      name: 'no-circular',
      severity: 'error',
      comment: 'Circular dependencies make code hard to reason about, test and tree-shake.',
      from: {},
      to: { circular: true },
    },
    {
      name: 'no-orphans',
      severity: 'warn',
      comment: 'Orphan modules are usually dead code. Confirm or delete.',
      from: {
        orphan: true,
        pathNot: ['\\.d\\.ts$', '(^|/)(index|layout|page|route|error|loading|not-found)\\.[jt]sx?$', '\\.config\\.[jt]s$'],
      },
      to: {},
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    ...(fs.existsSync(path.join(__dirname, 'tsconfig.json'))
      ? { tsConfig: { fileName: path.join(__dirname, 'tsconfig.json') } }
      : {}),
    enhancedResolveOptions: { extensions: ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx'] },
  },
};
