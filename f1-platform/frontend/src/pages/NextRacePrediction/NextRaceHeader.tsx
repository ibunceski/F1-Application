import { CalendarClock, Flag } from 'lucide-react';
import { CountryFlag } from '../../components/ui/CountryFlag';
import type { Race } from '../../types';

interface NextRaceHeaderProps {
  race: Race;
  daysUntilRace: number;
}

function formatRaceDate(value: string) {
  return new Intl.DateTimeFormat('en', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}

function countdownLabel(days: number) {
  if (days === 0) return 'Race day';
  if (days === 1) return 'Tomorrow';
  return `${days} days`;
}

export function NextRaceHeader({ race, daysUntilRace }: NextRaceHeaderProps) {
  return (
    <header className="space-y-4 border-b border-f1-border pb-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-widest text-f1-red">
            Round {race.round_number} - {formatRaceDate(race.race_date)}
          </p>
          <div className="mt-2 flex min-w-0 items-center gap-3">
            <CountryFlag country={race.circuit_country} className="text-2xl" />
            <h1 className="truncate text-3xl font-bold text-f1-white">{race.race_name}</h1>
          </div>
          <p className="mt-2 text-sm text-f1-muted">
            {race.circuit_name}, {race.circuit_location}, {race.circuit_country}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:w-80">
          <div className="card-elevated p-4">
            <div className="flex items-center gap-2 text-f1-muted">
              <CalendarClock className="h-4 w-4" />
              <p className="section-label">Countdown</p>
            </div>
            <p className="data-value mt-2 text-2xl">{countdownLabel(daysUntilRace)}</p>
          </div>
          <div className="card-elevated p-4">
            <div className="flex items-center gap-2 text-f1-muted">
              <Flag className="h-4 w-4" />
              <p className="section-label">Circuit</p>
            </div>
            <p className="mt-2 truncate text-sm font-semibold text-f1-white">{race.circuit_name}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
