import { useQueries, useQuery } from '@tanstack/react-query';
import { CalendarClock, Zap } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { getDriversBySeason } from '../../api/drivers';
import { getNextRace, getRaceResults, getRacesBySeason } from '../../api/races';
import { getSeasonStats } from '../../api/seasons';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { ApiError } from '../../lib/api';
import type { Race, RaceResult } from '../../types';
import { RaceCalendar } from './RaceCalendar';
import { SeasonStandings } from './SeasonStandings';
import { SeasonStats } from './SeasonStats';

type ResultsByRace = Record<number, RaceResult[]>;

function startOfToday() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}

function completedRaces(races: Race[]) {
  const today = startOfToday();
  return races.filter((race) => new Date(race.race_date) < today);
}

function buildResultsMap(races: Race[], results: RaceResult[][]): ResultsByRace {
  return races.reduce<ResultsByRace>((acc, race, index) => {
    acc[race.id] = results[index] || [];
    return acc;
  }, {});
}

function winner(results: RaceResult[]) {
  return results.find((result) => result.finishing_position === 1);
}

function fastestLap(results: RaceResult[]) {
  return results.find((result) => result.fastest_lap);
}

function formatRaceDate(value: string) {
  return new Intl.DateTimeFormat('en', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}

function daysUntil(date: string) {
  const today = startOfToday();
  const target = new Date(date);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

function countdownLabel(days: number) {
  if (days === 0) return 'Race day';
  if (days === 1) return 'Tomorrow';
  return `${days} days`;
}

function isNotFound(error: unknown) {
  return (error as ApiError | undefined)?.status === 404;
}

function NextRaceCard({ race, isLoading, isMissing }: { race?: Race; isLoading: boolean; isMissing: boolean }) {
  if (isLoading) {
    return (
      <section className="card-elevated p-5">
        <div className="h-4 w-24 animate-pulse rounded bg-f1-elevated" />
        <div className="mt-4 h-8 w-64 animate-pulse rounded bg-f1-elevated" />
        <div className="mt-3 h-4 w-48 animate-pulse rounded bg-f1-elevated" />
      </section>
    );
  }

  if (isMissing || !race) {
    return (
      <section className="card-elevated p-5">
        <p className="section-label">Next Race</p>
        <h2 className="mt-2 text-2xl font-bold text-f1-white">No upcoming race found</h2>
        <p className="mt-2 text-sm text-f1-muted">Ingest the latest race calendar to unlock next race predictions.</p>
      </section>
    );
  }

  const countdown = daysUntil(race.race_date);

  return (
    <section className="card-elevated overflow-hidden p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-f1-red">
            <CalendarClock className="h-4 w-4" />
            <p className="section-label text-f1-red">Next Race</p>
          </div>
          <h2 className="mt-3 text-3xl font-bold text-f1-white">{race.race_name}</h2>
          <p className="mt-2 text-sm text-f1-muted">
            {race.circuit_name}, {race.circuit_country} - {formatRaceDate(race.race_date)}
          </p>
        </div>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="rounded-md border border-f1-border bg-f1-surface px-4 py-3">
            <p className="section-label">Countdown</p>
            <p className="data-value mt-1 text-2xl text-f1-red">{countdownLabel(countdown)}</p>
          </div>
          <Link
            to="/predictions/next-race"
            className="inline-flex items-center justify-center gap-2 rounded-md bg-f1-red px-5 py-3 text-sm font-bold text-white hover:bg-red-700"
          >
            <Zap className="h-4 w-4" />
            Predict Next Race
          </Link>
        </div>
      </div>
    </section>
  );
}

function QuickRaceCards({ year, races, resultsByRace }: { year: number; races: Race[]; resultsByRace: ResultsByRace }) {
  const lastThree = completedRaces(races).slice(-3).reverse();
  if (!lastThree.length) {
    return <EmptyState title="No completed races" description="Race summaries will appear once results are ingested." />;
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="section-label">Recent Race Summary</p>
        <Link to="/drivers/compare" className="rounded border border-f1-border px-3 py-2 text-xs font-semibold text-f1-muted hover:border-f1-red hover:text-f1-white">
          Compare Drivers
        </Link>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {lastThree.map((race) => {
          const results = resultsByRace[race.id] || [];
          const raceWinner = winner(results);
          const raceFastestLap = fastestLap(results);
          const gains = results
            .map((result) =>
              result.grid_position !== null && result.finishing_position !== null
                ? result.grid_position - result.finishing_position
                : 0,
            )
            .slice(0, 8);

          return (
            <div key={race.id} className="card relative overflow-hidden p-4">
              <div className="absolute inset-x-0 bottom-0 flex h-10 items-end opacity-20">
                {gains.map((gain, index) => (
                  <div
                    key={index}
                    className="mx-0.5 flex-1 bg-f1-red"
                    style={{ height: `${Math.max(8, Math.min(40, 20 + gain * 3))}px` }}
                  />
                ))}
              </div>
              <div className="relative z-10">
                <p className="section-label">Round {race.round_number}</p>
                <h3 className="mt-2 font-semibold text-f1-white">{race.race_name}</h3>
                <div className="mt-4 space-y-2 text-sm">
                  <p className="text-f1-muted">Winner <span className="text-f1-text">{raceWinner ? `${raceWinner.driver.full_name} · ${raceWinner.team.short_name}` : '--'}</span></p>
                  <p className="text-f1-muted">Fastest Lap <span className="text-f1-text">{raceFastestLap?.driver.full_name || '--'}</span></p>
                </div>
                <Link
                  to={`/seasons/${year}/races/${race.id}/analysis`}
                  className="mt-4 inline-flex rounded bg-f1-elevated px-3 py-2 text-xs font-semibold text-f1-white hover:bg-f1-red"
                >
                  View Analysis
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function SeasonOverview() {
  const year = Number(useParams().year || 2024);
  const season = useQuery({ queryKey: ['season', year], queryFn: () => getSeasonStats(year) });
  const races = useQuery({ queryKey: ['races', year], queryFn: () => getRacesBySeason(year) });
  const drivers = useQuery({ queryKey: ['drivers', year], queryFn: () => getDriversBySeason(year) });
  const nextRace = useQuery({ queryKey: ['next-race'], queryFn: getNextRace, retry: 1 });
  const completed = completedRaces(races.data || []);
  const resultQueries = useQueries({
    queries: completed.map((race) => ({
      queryKey: ['race-results', race.id],
      queryFn: () => getRaceResults(race.id),
      staleTime: 5 * 60 * 1000,
    })),
  });
  const resultsByRace = buildResultsMap(
    completed,
    resultQueries.map((query) => query.data || []),
  );
  const resultsLoading = resultQueries.some((query) => query.isLoading);

  if (season.isLoading && races.isLoading && drivers.isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <header className="border-b border-f1-border pb-4">
        <p className="section-label">Season Dashboard</p>
        <h1 className="mt-2 inline-block border-b-2 border-f1-red pb-2 text-3xl font-bold text-f1-white">
          {year} Formula 1 Season
        </h1>
      </header>

      {season.isError || races.isError || drivers.isError ? <ErrorState message="Some season data could not be loaded." /> : null}

      <NextRaceCard
        race={nextRace.data}
        isLoading={nextRace.isLoading}
        isMissing={nextRace.isError && isNotFound(nextRace.error)}
      />

      <SeasonStats
        season={season.data?.season}
        races={races.data || []}
        drivers={drivers.data || []}
        isLoading={season.isLoading || races.isLoading || drivers.isLoading}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.8fr)]">
        <RaceCalendar year={year} races={races.data || []} resultsByRace={resultsByRace} isLoading={races.isLoading} />
        <SeasonStandings resultsByRace={resultsByRace} isLoading={resultsLoading} />
      </div>

      <QuickRaceCards year={year} races={races.data || []} resultsByRace={resultsByRace} />
    </div>
  );
}
