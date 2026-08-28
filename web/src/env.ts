import { createEnv } from '@t3-oss/env-core';
import { z } from 'zod';

// Imported from the root layout so it runs at boot: a missing or malformed variable throws before
// the console serves anything, rather than deep inside a request that is holding someone's letter.
// runtimeEnv is written out key by key because the bundler only inlines literal process.env reads.
export const env = createEnv({
  server: {
    NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
    PLAINLETTER_AGENT_ENDPOINT: z.url().default('http://127.0.0.1:8080'),
    // The deployed agent. When set, the proxy signs calls to it and the endpoint above is unused.
    PLAINLETTER_AGENT_RUNTIME_ARN: z
      .string()
      .regex(/^arn:aws:bedrock-agentcore:[a-z0-9-]+:\d{12}:runtime\/[A-Za-z0-9_-]+$/)
      .optional(),
    // Set this only when a proxy really does sit in front of this app and append the caller to
    // X-Forwarded-For. Left off, every caller is metered as one, which is stricter rather than
    // looser, and a forgotten setting should fail in that direction.
    PLAINLETTER_TRUST_PROXY_HEADER: z.enum(['true', 'false']).default('false'),
    // Who answers for the data, which is a fact about the deployment and not about the code: a
    // library running its own copy is its own controller. Left unset, the privacy page says the
    // operator of that desk is the controller and tells the visitor to ask at the counter, which
    // is true of every deployment. Set them and it names that operator instead. Naming one
    // organisation in the source would put a false name in front of every other deployment's
    // visitors, at the exact line where the law wants a real one.
    PLAINLETTER_CONTROLLER_NAME: z.string().min(1).optional(),
    PLAINLETTER_CONTROLLER_CONTACT: z.string().min(1).optional(),
    // Article 37 makes a data protection officer compulsory for a public authority or body, except
    // a court acting in its judicial capacity, and Article 37(7) makes publishing their contact
    // details compulsory with it. Whether it applies is a fact about the operator, so it is
    // configured here for the same reason the controller is: a municipality running its own copy
    // would otherwise publish a page saying it has not named one.
    //
    // An email address, and checked as one, because the page turns it into a link somebody clicks.
    // Any non-empty string would pass validation and then be written into a `mailto:`, so a phone
    // number or a contact-page address would render as a link that goes nowhere while the page said
    // the officer could be reached there, which is worse than saying nothing. An operator whose
    // officer publishes something other than an email should point this at a mailbox that reaches
    // them.
    PLAINLETTER_DPO_CONTACT: z.email().optional(),
  },
  clientPrefix: 'NEXT_PUBLIC_',
  client: {
    NEXT_PUBLIC_SITE_URL: z.url().default('http://localhost:3000'),
  },
  runtimeEnv: {
    NODE_ENV: process.env.NODE_ENV,
    PLAINLETTER_AGENT_ENDPOINT: process.env.PLAINLETTER_AGENT_ENDPOINT,
    PLAINLETTER_AGENT_RUNTIME_ARN: process.env.PLAINLETTER_AGENT_RUNTIME_ARN,
    PLAINLETTER_TRUST_PROXY_HEADER: process.env.PLAINLETTER_TRUST_PROXY_HEADER,
    PLAINLETTER_CONTROLLER_NAME: process.env.PLAINLETTER_CONTROLLER_NAME,
    PLAINLETTER_CONTROLLER_CONTACT: process.env.PLAINLETTER_CONTROLLER_CONTACT,
    PLAINLETTER_DPO_CONTACT: process.env.PLAINLETTER_DPO_CONTACT,
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
  },
  emptyStringAsUndefined: true,
});

// The two controller values are one disclosure, and half of one is not a smaller version of it.
// Article 13(1)(a) asks for the identity AND the contact details together: a name with no way to
// reach it leaves a visitor knowing who holds their letter and unable to ask anything, and a
// contact address with no name would have been dropped on the floor by the page. Either both or
// neither, found out here at boot rather than by somebody reading half a sentence at a desk.
if (Boolean(env.PLAINLETTER_CONTROLLER_NAME) !== Boolean(env.PLAINLETTER_CONTROLLER_CONTACT)) {
  throw new Error(
    'PLAINLETTER_CONTROLLER_NAME and PLAINLETTER_CONTROLLER_CONTACT must be set together, or ' +
      'both left unset. The privacy page names a controller only when it has both.',
  );
}
