import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getTyreStrategy } from '../../api/analysis';
import { getRaceById, getRaceResults } from '../../api/races';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { DriverTyreStrategy } from '../../types';
import { CompoundPaceChart } from './CompoundPaceChart';
import { PitStopTable } from './PitStopTable';
import { StrategyLegend } from './StrategyLegend';
import { StrategyTimeline } from './StrategyTimeline';
import { pitStopCount, strategyPattern } from './tyreUtils';

function strategyStats(strategies: DriverTyreStrategy[]) {
  const patternCounts = new Map<string, number>();
  const pitStops: { lap: number; driver: string }[] = [];
  const stopCounts = new Map<number, number>();

  strategies.forEach((strategy) => {
    const pattern = strategyPattern(strategy.stints);
    const stops = pitStopCount(strategy.stints);
    patternCounts.set(pattern, (patternCounts.get(pattern) || 0) + 1);
    stopCounts.set(stops, (stopCounts.get(stops) || 0) + 1);

    strategy.stints.slice(1).forEach((_, index) => {
      const previousStint = strategy.stints[index];
      pitStops.push({ lap: previousStint.end_lap, driver: strategy.abbreviation });
    });
  });

  const mostCommon = [...patternCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || '--';
  const earliest = [...pitStops].sort((a, b) => a.lap - b.lap)[0];
  const latest = [...pitStops].sort((a, b) => b.lap - a.lap)[0];
  const stopSummary = [...stopCounts.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([stops, count]) => `${count} using ${stops}-stop`)
    .join(' / ');

  return { mostCommon, earliest, latest, stopSummary };
}

function raceHasHappened(raceDate?: string) {
  if (!raceDate) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(raceDate);
  target.setHours(0, 0, 0, 0);
  return target < today;
}

export function TyreStrategy() {
  const raceId = Number(useParams().raceId);
  const race = useQuery({ queryKey: ['race', raceId], queryFn: () => getRaceById(raceId) });
  const canLoadStrategy = raceHasHappened(race.data?.race_date);
  const strategy = useQuery({
    queryKey: ['tyre-strategy', raceId],
    queryFn: () => getTyreStrategy(raceId),
    enabled: canLoadStrategy,
  });
  const results = useQuery({
    queryKey: ['race-results', raceId],
    queryFn: () => getRaceResults(raceId),
    enabled: canLoadStrategy,
  });

  if (race.isLoading || strategy.isLoading || results.isLoading) return <LoadingSpinner />;
  if (race.data && !canLoadStrategy) {
    return (
      <div className="space-y-6">
        <header className="border-b border-f1-border pb-4">
          <p className="font-mono text-xs font-semibold uppercase tracking-widest text-f1-red">
            Round {race.data.round_number} / {race.data.race_name}
          </p>
          <h1 className="mt-2 text-3xl font-bold text-f1-white">{race.data.circuit_name} - Tyre Strategy</h1>
        </header>
        <EmptyState
          title="Race has not happened yet"
          description="Tyre strategy is available after race results, lap data, and stint data are ingested."
        />
      </div>
    );
  }
  if (race.isError || strategy.isError || results.isError) {
    return <ErrorState message="Tyre strategy data could not be loaded." />;
  }

  const strategies = strategy.data || [];
  const raceResults = results.data || [];
  const totalLaps = Math.max(
    ...raceResults.map((result) => result.laps_completed),
    ...strategies.flatMap((item) => item.stints.map((stint) => stint.end_lap)),
    0,
  );
  const stats = strategyStats(strategies);

  return (
    <div className="space-y-6">
      <header className="border-b border-f1-border pb-4">
        <p className="font-mono text-xs font-semibold uppercase tracking-widest text-f1-red">
          Round {race.data?.round_number} / {race.data?.race_name}
        </p>
        <h1 className="mt-2 text-3xl font-bold text-f1-white">{race.data?.circuit_name} - Tyre Strategy</h1>
      </header>

      <StrategyLegend strategies={strategies} />
      <StrategyTimeline strategies={strategies} totalLaps={totalLaps} results={raceResults} />

      <div className="grid gap-4 md:grid-cols-4">
        <div className="card p-4">
          <p className="section-label">Most Common</p>
          <p className="mt-2 text-sm font-semibold text-f1-white">{stats.mostCommon}</p>
        </div>
        <div className="card p-4">
          <p className="section-label">Earliest Pit Stop</p>
          <p className="mt-2 data-value">{stats.earliest ? `Lap ${stats.earliest.lap} (${stats.earliest.driver})` : '--'}</p>
        </div>
        <div className="card p-4">
          <p className="section-label">Latest Pit Stop</p>
          <p className="mt-2 data-value">{stats.latest ? `Lap ${stats.latest.lap} (${stats.latest.driver})` : '--'}</p>
        </div>
        <div className="card p-4">
          <p className="section-label">Stop Counts</p>
          <p className="mt-2 text-sm text-f1-text">{stats.stopSummary || '--'}</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <CompoundPaceChart strategies={strategies} />
        <PitStopTable strategies={strategies} results={raceResults} />
      </div>
    </div>
  );
}
