import { Link } from 'react-router-dom';
import type { Race, RaceResult } from '../../types';

type ResultsByRace = Record<number, RaceResult[]>;

interface RaceCalendarProps {
  year: number;
  races: Race[];
  resultsByRace: ResultsByRace;
  selectedRaceId?: number;
  isLoading?: boolean;
}

function startOfToday() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}

function daysUntil(date: string) {
  const today = startOfToday();
  const target = new Date(date);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

function monthLabel(date: string) {
  return new Intl.DateTimeFormat('en', { month: 'long' }).format(new Date(date));
}

function shortDate(date: string) {
  return new Intl.DateTimeFormat('en', { day: '2-digit', month: 'short' }).format(new Date(date));
}

function nextRaceId(races: Race[]) {
  const today = startOfToday();
  return races.find((race) => new Date(race.race_date) >= today)?.id;
}

function statusBadge(isCompleted: boolean, isNext: boolean) {
  if (isNext) {
    return <span className="rounded-full bg-f1-red px-2 py-1 text-[0.65rem] font-bold text-white animate-pulse">NEXT</span>;
  }
  if (isCompleted) {
    return <span className="rounded-full bg-compound-inter/15 px-2 py-1 text-[0.65rem] font-bold text-compound-inter">COMPLETED</span>;
  }
  return <span className="rounded-full bg-podium-bronze/15 px-2 py-1 text-[0.65rem] font-bold text-podium-bronze">UPCOMING</span>;
}

function roundClass(isCompleted: boolean, isNext: boolean) {
  if (isNext) return 'bg-f1-red text-white';
  if (isCompleted) return 'bg-f1-elevated text-f1-muted';
  return 'border border-f1-border bg-transparent text-f1-muted';
}

export function RaceCalendar({ year, races, resultsByRace, selectedRaceId, isLoading }: RaceCalendarProps) {
  if (isLoading) {
    return (
      <section className="card p-4">
        <div className="mb-4 h-4 w-32 animate-pulse rounded bg-f1-elevated" />
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={index} className="h-16 animate-pulse rounded bg-f1-elevated" />
          ))}
        </div>
      </section>
    );
  }

  const today = startOfToday();
  const nextId = nextRaceId(races);
  let currentMonth = '';

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-f1-border px-4 py-3">
        <p className="section-label">Race Calendar</p>
      </div>
      <div className="divide-y divide-f1-border">
        {races.map((race) => {
          const raceDate = new Date(race.race_date);
          const isCompleted = raceDate < today;
          const isNext = race.id === nextId;
          const month = monthLabel(race.race_date);
          const showMonth = month !== currentMonth;
          currentMonth = month;
          const results = resultsByRace[race.id] || [];
          const winner = results.find((result) => result.finishing_position === 1);
          const target = isCompleted
            ? `/seasons/${year}/races/${race.id}/analysis`
            : `/seasons/${year}/races/${race.id}/predict`;

          return (
            <div key={race.id}>
              {showMonth ? <div className="bg-f1-dark px-4 py-2 text-xs font-semibold uppercase tracking-widest text-f1-muted">{month}</div> : null}
              <Link
                to={target}
                className={`grid grid-cols-[44px_1fr_auto] items-center gap-3 px-4 py-3 transition hover:bg-f1-elevated/60 ${
                  isCompleted ? 'opacity-70' : ''
                } ${isNext || selectedRaceId === race.id ? 'border-l-2 border-f1-red' : 'border-l-2 border-transparent'}`}
              >
                <span className={`flex h-8 w-8 items-center justify-center rounded-full font-mono text-xs font-bold ${roundClass(isCompleted, isNext)}`}>
                  {race.round_number}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-f1-white">{race.race_name}</p>
                    {statusBadge(isCompleted, isNext)}
                  </div>
                  <p className="mt-1 truncate text-xs text-f1-muted">
                    {race.circuit_location}, {race.circuit_country} · {shortDate(race.race_date)}
                  </p>
                  {winner ? <p className="mt-1 text-xs text-f1-muted">P1 {winner.driver.full_name}</p> : null}
                </div>
                <div className="text-right">
                  {isNext ? <p className="data-value text-xs text-f1-red">In {daysUntil(race.race_date)} days</p> : null}
                  {!isCompleted && !isNext ? <span className="rounded border border-f1-border px-3 py-1 text-xs text-f1-text">Predict</span> : null}
                </div>
              </Link>
            </div>
          );
        })}
      </div>
    </section>
  );
}
