import { PositionBadge } from '../../components/ui/PositionBadge';
import { formatPoints } from '../../lib/formatters';
import type { PredictionDriverComparison } from '../../types';
import { teamColor } from '../RacePredictor/teamColors';
import { PredictionOutcomeBadges } from './PredictionOutcomeBadges';

interface PredictionComparisonTableProps {
  drivers: PredictionDriverComparison[];
}

function errorClass(value: number | null) {
  const error = Math.abs(value ?? 0);
  if (error <= 1) return 'text-compound-inter';
  if (error <= 3) return 'text-podium-bronze';
  return 'text-f1-red';
}

export function PredictionComparisonTable({ drivers }: PredictionComparisonTableProps) {
  const sorted = [...drivers].sort((a, b) => a.predicted_rank - b.predicted_rank);

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-f1-border px-4 py-3">
        <p className="section-label">Driver Comparison</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-left text-sm">
          <thead className="bg-f1-elevated text-xs uppercase text-f1-muted">
            <tr>
              <th className="px-4 py-3">Driver</th>
              <th className="px-4 py-3">Team</th>
              <th className="px-4 py-3">Predicted Rank</th>
              <th className="px-4 py-3">Actual Finish</th>
              <th className="px-4 py-3">Error</th>
              <th className="px-4 py-3">Podium</th>
              <th className="px-4 py-3">Top 10</th>
              <th className="px-4 py-3">Points</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-f1-border">
            {sorted.map((row) => (
              <tr key={row.driver.id} className={row.predicted_rank <= 3 ? 'border-l-2 border-podium-bronze bg-podium-bronze/5' : 'border-l-2 border-transparent'}>
                <td className="px-4 py-4">
                  <p className="font-semibold text-f1-white">{row.driver.full_name}</p>
                  <p className="text-xs text-f1-muted">{row.driver.abbreviation}</p>
                </td>
                <td className="px-4 py-4">
                  <span className="border-l-4 pl-3 text-f1-text" style={{ borderColor: teamColor(row.team.name) }}>
                    {row.team.short_name || row.team.name}
                  </span>
                </td>
                <td className="px-4 py-4">
                  <PositionBadge position={row.predicted_rank} />
                </td>
                <td className="px-4 py-4">
                  {row.actual_position ?? row.actual_rank ? (
                    <PositionBadge position={(row.actual_position ?? row.actual_rank) as number} />
                  ) : (
                    <span className="text-f1-muted">--</span>
                  )}
                </td>
                <td className={`data-value px-4 py-4 ${errorClass(row.position_error)}`}>
                  {row.position_error === null ? '--' : Math.abs(row.position_error).toFixed(1)}
                </td>
                <td className="px-4 py-4">
                  <PredictionOutcomeBadges predictedPodium={row.predicted_podium} actualPodium={row.actual_podium} compact />
                </td>
                <td className="px-4 py-4">
                  <PredictionOutcomeBadges predictedTop10={row.predicted_top10} actualTop10={row.actual_top10} compact />
                </td>
                <td className="data-value px-4 py-4">{formatPoints(row.points)}</td>
                <td className="px-4 py-4 text-f1-muted">{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
