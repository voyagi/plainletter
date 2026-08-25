import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// The Content-Security-Policy, built per request because it carries a nonce.
//
// Scripts are where the strictness lives: a fresh nonce plus strict-dynamic, so the only scripts
// that run are the ones this server put on the page and whatever they load. Next.js reads the nonce
// out of this header during rendering and attaches it to its own bundles, and the theme script in
// the layout asks for it by name. That is also why every page is rendered per request: a nonce
// baked at build time would be the same for everyone, which is the one thing a nonce may not be.
//
// Styles are deliberately not nonced. The desk card is a self-contained document that has to print
// from a phone, a library PC or a file on a stick with no server behind it, so its stylesheet is
// inline by necessity, and it is shown in a srcdoc frame which inherits this policy. A nonce on
// style-src would silently strip the printed card of its layout. A nonce and 'unsafe-inline'
// cannot be combined either: a browser that sees the nonce ignores the keyword.
function policy(nonce: string, isDev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ''}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    // The console posts letters to this application and nowhere else. The signing, the region and
    // the endpoint live on the server, so a browser that reaches another host is a browser that has
    // been taken over.
    "connect-src 'self'",
    "frame-src 'self'",
    "frame-ancestors 'self'",
    "form-action 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    ...(isDev ? [] : ['upgrade-insecure-requests']),
  ].join('; ');
}

export function proxy(request: NextRequest): NextResponse {
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64');
  const header = policy(nonce, process.env.NODE_ENV === 'development');

  // The nonce travels on the request so the layout can put it on the theme script, and on the
  // response so the browser enforces it.
  const headers = new Headers(request.headers);
  headers.set('x-nonce', nonce);
  headers.set('Content-Security-Policy', header);

  const response = NextResponse.next({ request: { headers } });
  response.headers.set('Content-Security-Policy', header);
  return response;
}

export const config = {
  matcher: [
    {
      // Everything that renders a document. The upload route answers with an event stream and sets
      // its own headers, and the static assets under _next are files.
      source: '/((?!api|_next/static|_next/image|favicon.ico).*)',
      missing: [
        { type: 'header', key: 'next-router-prefetch' },
        { type: 'header', key: 'purpose', value: 'prefetch' },
      ],
    },
  ],
};
