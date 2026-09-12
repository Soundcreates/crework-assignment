import Link from "next/link";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-3xl py-16">
      <p className="text-sm uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">
        Internal sales radar
      </p>
      <h1 className="mt-4 text-5xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
        Lead Intelligence
      </h1>
      <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-600 dark:text-zinc-300">
        Discover companies showing buying-intent signals — funding, sales
        hiring, and expansion — then rank who to contact first with
        evidence-backed scores.
      </p>
      <div className="mt-8 flex gap-3">
        <Link
          href="/dashboard"
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
        >
          Open dashboard
        </Link>
        <Link
          href="/discover"
          className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
        >
          Run discovery
        </Link>
      </div>
    </div>
  );
}
