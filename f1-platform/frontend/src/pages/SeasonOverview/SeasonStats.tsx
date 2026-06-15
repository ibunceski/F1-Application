import { StatCard } from '../../components/ui/StatCard';
import type { Driver, Race, Season } from '../../types';

function startOfToday() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}

function completedRaces(races: Race[]) {
  const today = startOfToday();
  return races.filter((race) => new Date(race.race_date) < today).length;
}

interface SeasonStatsProps {
  season?: Season;
  races: Race[];
  drivers: Driver[];
  isLoading?: boolean;
}

export function SeasonStats({ season, races, drivers, isLoading }: SeasonStatsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="card h-28 animate-pulse bg-f1-elevated" />
        ))}
      </div>
    );
  }

  const completed = completedRaces(races);
  const total = season?.total_races ?? races.length;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Total Races" value={total} />
      <StatCard label="Drivers" value={drivers.length} />
      <StatCard label="Races Completed" value={completed} />
      <StatCard label="Races Remaining" value={Math.max(total - completed, 0)} />
    </div>
  );
}
