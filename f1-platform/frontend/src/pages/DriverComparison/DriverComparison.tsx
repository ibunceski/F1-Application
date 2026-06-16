import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { compareDrivers, getLapTimes } from '../../api/analysis';
import { getDriversBySeason } from '../../api/drivers';
import { getRaceResults, getRacesBySeason } from '../../api/races';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { ComparisonSelector } from './ComparisonSelector';
import { HeadToHeadStats } from './HeadToHeadStats';
import { LapTimeDeltaChart } from './LapTimeDeltaChart';
import { RacePaceDistribution } from './RacePaceDistribution';
import { SectorComparisonChart } from './SectorComparisonChart';

function numberParam(value: string | null) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function defaultSeason() {
  return Math.min(Math.max(new Date().getFullYear(), 2021), 2026);
}

function EmptyComparisonState() {
  return (
    <div className="card flex min-h-72 flex-col items-center justify-center gap-5 p-8 text-center">
      <svg viewBox="0 0 220 120" className="h-28 w-52 text-f1-muted" aria-hidden="true">
        <path
          d="M35 70 C35 25 92 16 128 30 C178 50 190 100 133 102 C80 104 55 92 35 70Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
        />
        <path d="M68 70 C92 48 126 50 151 73" fill="none" stroke="#E8002D" strokeWidth="3" strokeDasharray="8 7" />
      </svg>
      <EmptyState title="Select a race and two drivers to begin" description="Choose completed race data to unlock the head-to-head comparison." />
    </div>
  );
}

function SkeletonPanels() {
  return (
    <div className="space-y-5">
      <div className="h-72 animate-pulse rounded-lg bg-f1-elevated" />
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="h-80 animate-pulse rounded-lg bg-f1-elevated" />
        <div className="h-80 animate-pulse rounded-lg bg-f1-elevated" />
      </div>
    </div>
  );
}

export function DriverComparison() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [season, setSeason] = useState(defaultSeason);
  const [selectedRaceId, setSelectedRaceId] = useState<number | null>(() => numberParam(searchParams.get('raceId')));
  const [driver1Id, setDriver1Id] = useState<number | null>(() => numberParam(searchParams.get('driver1')));
  const [driver2Id, setDriver2Id] = useState<number | null>(() => numberParam(searchParams.get('driver2')));

  const races = useQuery({ queryKey: ['races', season], queryFn: () => getRacesBySeason(season) });
  const drivers = useQuery({ queryKey: ['drivers', season], queryFn: () => getDriversBySeason(season) });
  const raceResults = useQuery({
    queryKey: ['race-results', selectedRaceId],
    queryFn: () => getRaceResults(selectedRaceId as number),
    enabled: Boolean(selectedRaceId),
  });
  const comparison = useQuery({
    queryKey: ['driver-comparison', selectedRaceId, driver1Id, driver2Id],
    queryFn: () => compareDrivers(selectedRaceId as number, driver1Id as number, driver2Id as number),
    enabled: Boolean(selectedRaceId && driver1Id && driver2Id),
    retry: 1,
  });
  const lapTimesD1 = useQuery({
    queryKey: ['lap-times', selectedRaceId, driver1Id],
    queryFn: () => getLapTimes(selectedRaceId as number, driver1Id as number),
    enabled: Boolean(selectedRaceId && driver1Id),
  });
  const lapTimesD2 = useQuery({
    queryKey: ['lap-times', selectedRaceId, driver2Id],
    queryFn: () => getLapTimes(selectedRaceId as number, driver2Id as number),
    enabled: Boolean(selectedRaceId && driver2Id),
  });

  const racedDrivers = useMemo(() => {
    const resultDrivers = raceResults.data || [];
    if (resultDrivers.length) return resultDrivers;
    const driverRows = drivers.data || [];
    return driverRows.map((driver) => ({
      id: driver.id,
      driver_id: driver.id,
      team_id: driver.team_id ?? 0,
      grid_position: null,
      finishing_position: null,
      classified_position: null,
      status: '',
      points: 0,
      laps_completed: 0,
      fastest_lap: false,
      fastest_lap_time_ms: null,
      driver,
      team: { id: driver.team_id ?? 0, name: 'Unknown', short_name: 'Unknown', nationality: null, constructor_id: 'unknown' },
    }));
  }, [drivers.data, raceResults.data]);

  function syncParams(raceId: number | null, d1: number | null, d2: number | null) {
    const next = new URLSearchParams();
    if (raceId) next.set('raceId', String(raceId));
    if (d1) next.set('driver1', String(d1));
    if (d2) next.set('driver2', String(d2));
    setSearchParams(next, { replace: true });
  }

  function setRace(raceId: number | null) {
    setSelectedRaceId(raceId);
    setDriver1Id(null);
    setDriver2Id(null);
    syncParams(raceId, null, null);
  }

  function setD1(driverId: number | null) {
    setDriver1Id(driverId);
    const nextD2 = driverId === driver2Id ? null : driver2Id;
    setDriver2Id(nextD2);
    syncParams(selectedRaceId, driverId, nextD2);
  }

  function setD2(driverId: number | null) {
    setDriver2Id(driverId);
    syncParams(selectedRaceId, driver1Id, driverId);
  }

  function reset() {
    setSelectedRaceId(null);
    setDriver1Id(null);
    setDriver2Id(null);
    setSearchParams({}, { replace: true });
  }

  function changeSeason(year: number) {
    setSeason(year);
    setSelectedRaceId(null);
    setDriver1Id(null);
    setDriver2Id(null);
    setSearchParams({}, { replace: true });
  }

  const selectionComplete = Boolean(selectedRaceId && driver1Id && driver2Id);
  const d1Laps = lapTimesD1.data?.[0]?.laps || [];
  const d2Laps = lapTimesD2.data?.[0]?.laps || [];

  return (
    <div className="space-y-6">
      <header className="border-b border-f1-border pb-4">
        <p className="section-label">Analysis Tool</p>
        <h1 className="mt-2 text-3xl font-bold text-f1-white">Driver Head-to-Head Comparison</h1>
      </header>

      <ComparisonSelector
        season={season}
        races={races.data || []}
        results={racedDrivers}
        selectedRaceId={selectedRaceId}
        driver1Id={driver1Id}
        driver2Id={driver2Id}
        onSeasonChange={changeSeason}
        onRaceChange={setRace}
        onDriver1Change={setD1}
        onDriver2Change={setD2}
        onCompare={() => syncParams(selectedRaceId, driver1Id, driver2Id)}
        onReset={reset}
      />

      {!selectionComplete ? <EmptyComparisonState /> : null}
      {selectionComplete && comparison.isLoading ? <SkeletonPanels /> : null}
      {comparison.isError ? <ErrorState message="No lap data available for this race yet" /> : null}

      {comparison.data ? (
        <div className="space-y-6">
          <HeadToHeadStats comparison={comparison.data} />
          <div className="grid gap-5 xl:grid-cols-2">
            <SectorComparisonChart comparison={comparison.data} />
            {lapTimesD1.isLoading || lapTimesD2.isLoading ? (
              <LoadingSpinner />
            ) : (
              <LapTimeDeltaChart
                lapTimesD1={d1Laps}
                lapTimesD2={d2Laps}
                d1Name={comparison.data.driver1.abbreviation}
                d2Name={comparison.data.driver2.abbreviation}
              />
            )}
          </div>
          <RacePaceDistribution
            lapTimesD1={d1Laps}
            lapTimesD2={d2Laps}
            d1Name={comparison.data.driver1.abbreviation}
            d2Name={comparison.data.driver2.abbreviation}
          />
        </div>
      ) : null}
    </div>
  );
}
