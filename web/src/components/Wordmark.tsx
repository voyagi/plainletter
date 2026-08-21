import Link from 'next/link';

export function Wordmark({ as = 'link' }: { as?: 'link' | 'text' }) {
  const mark = <span className="font-brand text-xl font-extrabold tracking-[-0.02em]">Plainletter</span>;
  return as === 'link' ? (
    <Link href="/" className="rounded-sm no-underline">
      {mark}
    </Link>
  ) : (
    mark
  );
}
