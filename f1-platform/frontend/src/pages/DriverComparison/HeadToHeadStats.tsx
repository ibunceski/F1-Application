import { formatGap, formatLapTime, formatPosition } from '../../lib/formatters';
import type { DriverComparisonResponse } from '../../types';
import { qualifyingStats, raceStats, sectorStats } from './comparisonUtils';

interface HeadToHeadStatsProps {
  comparison: DriverComparisonResponse;
}

type Better = 'lower' | 'higher';

function betterClass(left: number | null | undefined, right: number | null | undefined, side: 'left' | 'right', better: Better) {
  if (left === null || left === undefined || right === null || right === undefined || left === right) return 'text-f1-text';
  const leftBetter = better === 'lower' ? left < right : left > right;
  return (side === 'left' ? leftBetter : !leftBetter) ? 'text-green-400' : 'text-f1-text';
}

function value(value: number | null | undefined, formatter?: (value: number) => string) {
  if (value === null || value === undefined) return '--';
  return formatter ? formatter(value) : String(value);
}

export function HeadToHeadStats({ comparison }: HeadToHeadStatsProps) {
  const d1 = comparison.driver1;
  const d2 = comparison.driver2;
  const q1 = qualifyingStats(comparison, d1.driver_id);
  const q2 = qualifyingStats(comparison, d2.driver_id);
  const r1 = raceStats(comparison, d1.driver_id);
  const r2 = raceStats(comparison, d2.driver_id);
  const s1 = sectorStats(comparison, d1.driver_id);
  const s2 = sectorStats(comparison, d2.driver_id);
  const rows = [
    ['Qualifying Position', q1.position, q2.position, 'lower', (v: number) => formatPosition(v)],
    ['Gap to Pole', q1.gap_to_pole_ms, q2.gap_to_pole_ms, 'lower', formatGap],
    ['Grid Position', q1.position, q2.position, 'lower', (v: number) => formatPosition(v)],
    ['Finishing Position', r1.finishing_position, r2.finishing_position, 'lower', (v: number) => formatPosition(v)],
    ['Points Scored', r1.points, r2.points, 'higher', (v: number) => v.toFixed(1)],
    ['Fastest Lap Time', d1.best_lap_time_ms, d2.best_lap_time_ms, 'lower', formatLapTime],
    ['Avg Clean Lap Time', d1.avg_lap_time_ms, d2.avg_lap_time_ms, 'lower', formatLapTime],
    ['Sector 1 Avg Time', s1.avg_sector1_ms, s2.avg_sector1_ms, 'lower', formatLapTime],
    ['Sector 2 Avg Time', s1.avg_sector2_ms, s2.avg_sector2_ms, 'lower', formatLapTime],
    ['Sector 3 Avg Time', s1.avg_sector3_ms, s2.avg_sector3_ms, 'lower', formatLapTime],
    ['Total Laps Completed', d1.total_laps, d2.total_laps, 'higher', (v: number) => String(v)],
  ] as const;

  return (
    <section className="card overflow-hidden">
      <div className="grid grid-cols-[1fr_160px_1fr] border-b border-f1-border bg-f1-elevated px-4 py-4 text-center">
        <div className="border-l-4 border-compound-wet pl-3 text-left">
          <p className="text-lg font-bold text-f1-white">{d1.driver_name}</p>
          <p className="text-sm text-f1-muted">{d1.team_name}</p>
        </div>
        <p className="section-label self-center">Head to Head</p>
        <div className="border-r-4 border-podium-bronze pr-3 text-right">
          <p className="text-lg font-bold text-f1-white">{d2.driver_name}</p>
          <p className="text-sm text-f1-muted">{d2.team_name}</p>
        </div>
      </div>
      <div className="divide-y divide-f1-border">
        {rows.map(([label, left, right, better, formatter]) => (
          <div key={label} className="grid grid-cols-[1fr_160px_1fr] items-center px-4 py-3 text-sm">
            <p className={`data-value text-left ${betterClass(left, right, 'left', better)}`}>{value(left, formatter)}</p>
            <p className="text-center text-xs font-semibold uppercase tracking-wider text-f1-muted">{label}</p>
            <p className={`data-value text-right ${betterClass(left, right, 'right', better)}`}>{value(right, formatter)}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
