import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getFastestLaps, getLapTimes, getPositionChanges, getWeather } from '../../api/analysis';
import { getRaceById, getRaceQualifying, getRaceResults } from '../../api/races';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { formatDate } from '../../lib/formatters';
import type { RaceResult } from '../../types';
import { FastestLapsTable } from './FastestLapsTable';
import { LapTimeChart } from './LapTimeChart';
import { PositionChangesChart } from './PositionChangesChart';
import { RaceResultTable } from './RaceResultTable';
import { WeatherPanel } from './WeatherPanel';

function podium(results: RaceResult[], position: number) {
  return results.find((result) => result.finishing_position === position);
}

function PodiumCard({ result, position }: { result?: RaceResult; position: 1 | 2 | 3 }) {
  const gradient = position === 1
    ? 'from-podium-gold/30 to-f1-surface'
    : position === 2
      ? 'from-podium-silver/25 to-f1-surface'
      : 'from-podium-bronze/25 to-f1-surface';
  const size = position === 1 ? 'lg:scale-105 lg:-translate-y-2 shadow-[0_0_20px_rgba(255,215,0,0.2)]' : '';

  return (
    <div className={`card bg-gradient-to-br ${gradient} p-4 ${size}`}>
      <p className="section-label">P{position}</p>
      <h3 className="mt-3 text-lg font-bold text-f1-white">{result?.driver.full_name || '--'}</h3>
      <p className="mt-1 text-sm text-f1-muted">{result?.team.name || '--'}</p>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="section-label">Status</p>
          <p className="data-value mt-1">{result?.status || '--'}</p>
        </div>
        <div>
          <p className="section-label">Points</p>
          <p className="data-value mt-1">{result?.points.toFixed(1) || '--'}</p>
        </div>
      </div>
    </div>
  );
}

export function RaceAnalysis() {
  const raceId = Number(useParams().raceId);
  const race = useQuery({ queryKey: ['race', raceId], queryFn: () => getRaceById(raceId) });
  const results = useQuery({ queryKey: ['race-results', raceId], queryFn: () => getRaceResults(raceId) });
  const qualifying = useQuery({ queryKey: ['qualifying', raceId], queryFn: () => getRaceQualifying(raceId) });
  const positions = useQuery({ queryKey: ['position-changes', raceId], queryFn: () => getPositionChanges(raceId) });
  const lapTimes = useQuery({ queryKey: ['lap-times', raceId], queryFn: () => getLapTimes(raceId) });
  const weather = useQuery({ queryKey: ['weather', raceId], queryFn: () => getWeather(raceId) });
  const fastestLaps = useQuery({ queryKey: ['fastest-laps', raceId], queryFn: () => getFastestLaps(raceId) });

  if (race.isLoading || results.isLoading) return <LoadingSpinner />;
  if (race.isError || results.isError) return <ErrorState message="Race analysis could not be loaded." />;

  const raceResults = results.data || [];

  return (
    <div className="space-y-6">
      <header className="border-b border-f1-border pb-4">
        <p className="font-mono text-xs font-semibold uppercase tracking-widest text-f1-red">
          Round {race.data?.round_number} · {race.data?.circuit_name}
        </p>
        <h1 className="mt-2 text-3xl font-bold text-f1-white">{race.data?.race_name} — Race Result</h1>
        <p className="mt-1 text-sm text-f1-muted">
          {race.data?.race_date ? formatDate(race.data.race_date) : '--'}
          {qualifying.data?.length ? ` · ${qualifying.data.length} qualifiers` : ''}
        </p>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr_1fr_320px]">
        <PodiumCard result={podium(raceResults, 2)} position={2} />
        <PodiumCard result={podium(raceResults, 1)} position={1} />
        <PodiumCard result={podium(raceResults, 3)} position={3} />
        <WeatherPanel weather={weather.data} />
      </div>

      <RaceResultTable results={raceResults} />

      <div className="grid gap-6 xl:grid-cols-2">
        {positions.isLoading ? <LoadingSpinner /> : <PositionChangesChart positionChanges={positions.data || []} />}
        {fastestLaps.isLoading ? <LoadingSpinner /> : <FastestLapsTable fastestLaps={fastestLaps.data || []} />}
      </div>

      {lapTimes.isLoading ? <LoadingSpinner /> : <LapTimeChart lapTimes={lapTimes.data || []} results={raceResults} />}
    </div>
  );
}
