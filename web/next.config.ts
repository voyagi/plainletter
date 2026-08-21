import type { NextConfig } from 'next';

const config: NextConfig = {
  reactStrictMode: true,
  // The console handles letters, so the browser gets no more reach than it needs. The proxy route
  // that talks to the agent runs on the server, which is why connect-src stays same-origin.
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
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
