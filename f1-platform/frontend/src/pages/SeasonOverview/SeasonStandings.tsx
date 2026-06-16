import { useMemo, useState } from 'react';
import { TeamLogo } from '../../components/ui/TeamLogo';
import type { RaceResult } from '../../types';

type ResultsByRace = Record<number, RaceResult[]>;

interface DriverStanding {
  id: number;
  name: string;
  abbreviation: string;
  nationality: string | null;
  teamName: string;
  teamShortName: string;
  points: number;
}

interface ConstructorStanding {
  id: number;
  name: string;
  shortName: string;
  points: number;
}

interface SeasonStandingsProps {
  resultsByRace: ResultsByRace;
  isLoading?: boolean;
}

function countryFlag(value: string | null) {
  if (!value || value.length !== 2) return '';
  const codePoints = value
    .toUpperCase()
    .split('')
    .map((char) => 127397 + char.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}

function podiumClass(position: number) {
  if (position === 1) return 'text-podium-gold';
  if (position === 2) return 'text-podium-silver';
  if (position === 3) return 'text-podium-bronze';
  return 'text-f1-muted';
}

function buildStandings(resultsByRace: ResultsByRace) {
  const driverMap = new Map<number, DriverStanding>();
  const constructorMap = new Map<number, ConstructorStanding>();

  Object.values(resultsByRace)
    .flat()
    .forEach((result) => {
      const driver = driverMap.get(result.driver.id) || {
        id: result.driver.id,
        name: result.driver.full_name,
        abbreviation: result.driver.abbreviation,
        nationality: result.driver.nationality,
        teamName: result.team.name,
        teamShortName: result.team.short_name,
        points: 0,
      };
      driver.points += result.points;
      driver.teamName = result.team.name;
      driver.teamShortName = result.team.short_name;
      driverMap.set(result.driver.id, driver);

      const constructor = constructorMap.get(result.team.id) || {
        id: result.team.id,
        name: result.team.name,
        shortName: result.team.short_name,
        points: 0,
      };
      constructor.points += result.points;
      constructorMap.set(result.team.id, constructor);
    });

  return {
    drivers: [...driverMap.values()].sort((a, b) => b.points - a.points),
    constructors: [...constructorMap.values()].sort((a, b) => b.points - a.points),
  };
}

export function SeasonStandings({ resultsByRace, isLoading }: SeasonStandingsProps) {
  const [tab, setTab] = useState<'drivers' | 'constructors'>('drivers');
  const [showAll, setShowAll] = useState(false);
  const standings = useMemo(() => buildStandings(resultsByRace), [resultsByRace]);

  if (isLoading) {
    return (
      <section className="card p-4">
        <div className="mb-4 h-4 w-28 animate-pulse rounded bg-f1-elevated" />
        <div className="space-y-3">
          {Array.from({ length: 10 }).map((_, index) => (
            <div key={index} className="h-10 animate-pulse rounded bg-f1-elevated" />
          ))}
        </div>
      </section>
    );
  }

  const rows = tab === 'drivers' ? standings.drivers : standings.constructors;
  const visibleRows = showAll ? rows : rows.slice(0, 10);

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-f1-border px-4 py-3">
        <p className="section-label">Standings</p>
        <div className="flex rounded-md border border-f1-border bg-f1-dark p-1">
          {(['drivers', 'constructors'] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              className={`rounded px-3 py-1 text-xs font-semibold capitalize ${
                tab === item ? 'bg-f1-red text-white' : 'text-f1-muted hover:text-f1-text'
              }`}
            >
              {item === 'drivers' ? 'Drivers' : 'Constructors'}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-f1-muted">
            <tr>
              <th className="px-4 py-3">Pos</th>
              <th className="px-4 py-3">{tab === 'drivers' ? 'Driver' : 'Team'}</th>
              {tab === 'drivers' ? <th className="px-4 py-3">Team</th> : null}
              <th className="px-4 py-3 text-right">Points</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-f1-border">
            {visibleRows.map((row, index) => (
              <tr key={row.id}>
                <td className={`px-4 py-3 font-mono font-bold ${podiumClass(index + 1)}`}>{index + 1}</td>
                <td className="px-4 py-3 font-semibold text-f1-white">
                  {'abbreviation' in row ? (
                    <span>{row.name} <span className="text-f1-muted">{countryFlag(row.nationality)}</span></span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <TeamLogo teamName={row.name} shortName={row.shortName} />
                      {row.name}
                    </span>
                  )}
                </td>
                {'abbreviation' in row ? (
                  <td className="px-4 py-3 text-f1-muted">
                    <span className="inline-flex items-center gap-2">
                      <TeamLogo teamName={row.teamName} shortName={row.teamShortName} />
                      {row.teamName}
                    </span>
                  </td>
                ) : null}
                <td className="data-value px-4 py-3 text-right">{row.points.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 10 ? (
        <button
          type="button"
          onClick={() => setShowAll((value) => !value)}
          className="w-full border-t border-f1-border px-4 py-3 text-sm font-semibold text-f1-muted hover:text-f1-white"
        >
          {showAll ? 'Show less' : 'Show all'}
        </button>
      ) : null}
    </section>
  );
}
