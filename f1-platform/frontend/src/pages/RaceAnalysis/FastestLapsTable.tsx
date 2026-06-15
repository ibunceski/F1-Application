import { TyreBadge } from '../../components/ui/TyreBadge';
import { formatLapTime } from '../../lib/formatters';
import type { FastestLap } from '../../types';

interface FastestLapsTableProps {
  fastestLaps: FastestLap[];
}

export function FastestLapsTable({ fastestLaps }: FastestLapsTableProps) {
  const sorted = [...fastestLaps].sort((a, b) => (a.lap_time_ms ?? Infinity) - (b.lap_time_ms ?? Infinity));

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-f1-border px-4 py-3">
        <p className="section-label">Fastest Laps</p>
      </div>
      <table className="w-full text-left text-sm">
        <thead className="bg-f1-elevated text-xs uppercase text-f1-muted">
          <tr><th className="px-4 py-3">Rank</th><th>Driver</th><th>Team</th><th>Lap Time</th><th>Lap</th><th>Tyre</th></tr>
        </thead>
        <tbody className="divide-y divide-f1-border">
          {sorted.map((lap, index) => (
            <tr key={lap.driver.id} className={index === 0 ? 'bg-purple-500/10' : ''}>
              <td className="data-value px-4 py-3">{index + 1}</td>
              <td className="font-semibold text-f1-white">{lap.driver.abbreviation}</td>
              <td className="text-f1-muted">{lap.team?.name || '--'}</td>
              <td className="data-value">{formatLapTime(lap.lap_time_ms)}</td>
              <td className="data-value">{lap.lap_number}</td>
              <td><TyreBadge compound={lap.compound} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
