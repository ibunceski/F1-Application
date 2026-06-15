import { PositionBadge } from '../../components/ui/PositionBadge';
import { formatPosition } from '../../lib/formatters';
import type { RaceResult } from '../../types';

interface RaceResultTableProps {
  results: RaceResult[];
}

function countryFlag(value: string | null) {
  if (!value || value.length !== 2) return '';
  return String.fromCodePoint(...value.toUpperCase().split('').map((char) => 127397 + char.charCodeAt(0)));
}

function sortResults(results: RaceResult[]) {
  return [...results].sort((a, b) => {
    if (a.finishing_position !== null && b.finishing_position !== null) {
      return a.finishing_position - b.finishing_position;
    }
    if (a.finishing_position !== null) return -1;
    if (b.finishing_position !== null) return 1;
    return b.laps_completed - a.laps_completed;
  });
}

function gridDelta(result: RaceResult) {
  if (result.grid_position === null || result.finishing_position === null) return null;
  const delta = result.grid_position - result.finishing_position;
  if (delta === 0) return null;
  return <span className={delta > 0 ? 'text-compound-inter' : 'text-f1-red'}>{delta > 0 ? '+' : ''}{delta}</span>;
}

export function RaceResultTable({ results }: RaceResultTableProps) {
  const sorted = sortResults(results);
  const firstDnfIndex = sorted.findIndex((result) => result.finishing_position === null);

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-f1-border px-4 py-3">
        <p className="section-label">Final Classification</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-f1-elevated text-xs uppercase text-f1-muted">
            <tr>
              <th className="px-4 py-3">Position</th>
              <th className="px-4 py-3">Driver</th>
              <th className="px-4 py-3">Team</th>
              <th className="px-4 py-3">Grid</th>
              <th className="px-4 py-3">Laps</th>
              <th className="px-4 py-3">Status/Time</th>
              <th className="px-4 py-3">Points</th>
              <th className="px-4 py-3">Fastest Lap</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-f1-border">
            {sorted.map((result, index) => (
              <tr key={result.id} className={index === firstDnfIndex ? 'border-t-2 border-f1-border' : ''}>
                <td className="px-4 py-3">
                  {result.finishing_position ? <PositionBadge position={result.finishing_position} /> : <span className="text-f1-red">{result.classified_position || 'DNF'}</span>}
                </td>
                <td className="px-4 py-3">
                  <p className="font-semibold text-f1-white">{result.driver.full_name} <span className="text-f1-muted">{countryFlag(result.driver.nationality)}</span></p>
                  <p className="text-xs text-f1-muted">{result.driver.abbreviation}</p>
                </td>
                <td className="px-4 py-3 text-f1-muted">{result.team.name}</td>
                <td className="px-4 py-3">
                  <span className="data-value">{result.grid_position ?? '--'}</span>
                  <span className="ml-2 text-xs">{gridDelta(result)}</span>
                </td>
                <td className="data-value px-4 py-3">{result.laps_completed}</td>
                <td className="px-4 py-3 text-f1-muted">
                  {result.status === 'Finished' && result.finishing_position ? formatPosition(result.finishing_position) : result.status}
                </td>
                <td className="data-value px-4 py-3">{result.points.toFixed(1)}</td>
                <td className="px-4 py-3">
                  {result.fastest_lap ? <span className="rounded bg-purple-500/20 px-2 py-1 text-xs font-bold text-purple-300">FL</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
