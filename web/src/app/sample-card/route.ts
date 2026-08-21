import exported from '@/data/sample-reading.json';

// The desk card exactly as it leaves the agent, served on its own address so it can be printed,
// linked and measured. Rebuilding it here in React would put a second version of a visitor's
// deadline on the page, which is the one thing this product exists to prevent.
export const dynamic = 'force-static';

export function GET(): Response {
  return new Response(exported.desk_card_html, {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      // Revalidated rather than held: the card is small, and a stale copy of a deadline is the
      // one thing worth spending a round trip to avoid.
      'cache-control': 'public, max-age=0, must-revalidate',
    },
  });
}
