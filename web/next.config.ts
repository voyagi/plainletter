import type { NextConfig } from 'next';

const config: NextConfig = {
  reactStrictMode: true,
  // `next dev` writes two instruction files into this directory unless told not to. They are not
  // part of the product and nothing here reads them.
  agentRules: false,
  // The headers that are the same on every response. The Content-Security-Policy is not one of
  // them: it carries a per-request nonce and is built in `src/proxy.ts`.
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          // Two years, subdomains included, and preload-ready. A letter is uploaded over this
          // connection, so a single downgraded request is one too many.
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          // SAMEORIGIN rather than DENY: the landing page shows the real printed card in a frame,
          // which is the honest way to show what goes home with the visitor.
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'Permissions-Policy', value: 'camera=(self), microphone=(), geolocation=()' },
        ],
      },
    ];
  },
};

export default config;
