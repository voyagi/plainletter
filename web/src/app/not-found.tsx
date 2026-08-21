import Link from 'next/link';
import { Wordmark } from '@/components/Wordmark';

export default function NotFound() {
  return (
    <main className="mx-auto max-w-[40rem] px-7 pt-8 pb-16">
      <Wordmark />
      <h1 className="mt-10 mb-4 font-brand text-[clamp(28px,3.4vw,40px)] leading-[1.1] font-bold tracking-[-0.03em]">
        This page is not one of ours.
      </h1>
      <p className="m-0 mb-6 text-[17px] text-ink-2">
        The address you followed does not exist here. The letter, the desk and the privacy page all
        do.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link
          href="/"
          className="inline-block rounded-lg border border-ink bg-ink px-5 py-3 text-base font-bold text-paper no-underline"
        >
          Read the letter
        </Link>
        <Link
          href="/desk"
          className="inline-block rounded-lg border border-ink px-5 py-3 text-base font-bold no-underline"
        >
          Open the desk console
        </Link>
      </div>
    </main>
  );
}
