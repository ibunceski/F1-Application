import { Link } from 'react-router-dom';
import { useSeason } from '../contexts/useSeason';

export function NotFound() {
  const { currentSeason } = useSeason();

  return (
    <div className="flex min-h-screen items-center justify-center bg-f1-dark px-4">
      <div className="w-full max-w-lg rounded-lg border border-f1-border bg-f1-surface p-8 text-center shadow-2xl">
        <p className="font-mono text-sm font-semibold uppercase tracking-widest text-f1-red">404</p>
        <h1 className="mt-3 text-3xl font-bold text-f1-white">404 - Page Not Found</h1>
        <p className="mt-3 text-sm leading-relaxed text-f1-muted">The requested dashboard route does not exist.</p>
        <Link
          to={`/seasons/${currentSeason}`}
          className="mt-6 inline-flex rounded bg-f1-red px-4 py-2 text-sm font-semibold text-white"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
