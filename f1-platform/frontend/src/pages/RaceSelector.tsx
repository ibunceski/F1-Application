import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { getRacesBySeason } from '../api/races';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { formatDate } from '../lib/formatters';

type RaceView = 'predict' | 'analysis' | 'tyres';

const viewConfig: Record<RaceView, { title: string; description: string; action: string; path: string }> = {
  predict: {
    title: 'Select Race for Prediction',
    description: 'Choose a race weekend to generate or review ML predictions.',
    action: 'Open Predictor',
    path: 'predict',
  },
  analysis: {
    title: 'Select Race for Analysis',
    description: 'Choose a completed race to inspect classification, lap pace, weather, and position changes.',
    action: 'Open Analysis',
    path: 'analysis',
  },
  tyres: {
    title: 'Select Race for Tyre Strategy',
    description: 'Choose a race to view stint timelines, compound pace, and pit stop patterns.',
    action: 'Open Tyres',
    path: 'tyres',
  },
};

function parseView(value: string | null): RaceView {
  return value === 'analysis' || value === 'tyres' || value === 'predict' ? value : 'predict';
}

export function RaceSelector() {
  const year = Number(useParams().year || 2024);
  const [searchParams] = useSearchParams();
  const view = parseView(searchParams.get('view'));
  const config = viewConfig[view];
  const races = useQuery({ queryKey: ['races', year], queryFn: () => getRacesBySeason(year) });

  if (races.isLoading) return <LoadingSpinner />;
  if (races.isError) return <ErrorState message="Races could not be loaded." />;
  if (!races.data?.length) {
    return (
      <div className="space-y-4">
        <header>
          <p className="section-label">{year} Season</p>
          <h1 className="mt-2 text-2xl font-bold text-f1-white">{config.title}</h1>
          <p className="mt-2 text-sm text-f1-muted">{config.description}</p>
        </header>
        <EmptyState title="No races" description="Calendar data is not available. Run ingestion first, then refresh this page." />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="border-b border-f1-border pb-4">
        <p className="section-label">{year} Season</p>
        <h1 className="mt-2 text-2xl font-bold text-f1-white">{config.title}</h1>
        <p className="mt-2 text-sm text-f1-muted">{config.description}</p>
      </header>

      <div className="grid gap-3">
        {races.data.map((race) => (
          <Link
            key={race.id}
            to={`/seasons/${year}/races/${race.id}/${config.path}`}
            className="card grid grid-cols-[72px_1fr_auto] items-center gap-4 p-4 transition hover:border-f1-red hover:bg-f1-elevated"
          >
            <span className="data-value">R{race.round_number}</span>
            <div>
              <p className="font-semibold text-f1-white">{race.race_name}</p>
              <p className="text-sm text-f1-muted">
                {race.circuit_name} / {formatDate(race.race_date)}
              </p>
            </div>
            <span className="rounded bg-f1-red px-3 py-2 text-xs font-semibold text-white">{config.action}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
