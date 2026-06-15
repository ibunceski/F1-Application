import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatGap } from '../../lib/formatters';
import type { DriverComparisonResponse } from '../../types';
import { sectorStats } from './comparisonUtils';

interface SectorComparisonChartProps {
  comparison: DriverComparisonResponse;
}

export function SectorComparisonChart({ comparison }: SectorComparisonChartProps) {
  const d1 = comparison.driver1;
  const d2 = comparison.driver2;
  const s1 = sectorStats(comparison, d1.driver_id);
  const s2 = sectorStats(comparison, d2.driver_id);
  const data = [
    { sector: 'Sector 1', d1: (s1.avg_sector1_ms ?? 0) / 1000, d2: (s2.avg_sector1_ms ?? 0) / 1000, delta: (s1.avg_sector1_ms ?? 0) - (s2.avg_sector1_ms ?? 0) },
    { sector: 'Sector 2', d1: (s1.avg_sector2_ms ?? 0) / 1000, d2: (s2.avg_sector2_ms ?? 0) / 1000, delta: (s1.avg_sector2_ms ?? 0) - (s2.avg_sector2_ms ?? 0) },
    { sector: 'Sector 3', d1: (s1.avg_sector3_ms ?? 0) / 1000, d2: (s2.avg_sector3_ms ?? 0) / 1000, delta: (s1.avg_sector3_ms ?? 0) - (s2.avg_sector3_ms ?? 0) },
    { sector: 'Overall', d1: (d1.avg_lap_time_ms ?? 0) / 1000, d2: (d2.avg_lap_time_ms ?? 0) / 1000, delta: (d1.avg_lap_time_ms ?? 0) - (d2.avg_lap_time_ms ?? 0) },
  ];

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Sector Time Comparison</p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 24, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis dataKey="sector" stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <YAxis stroke="#6B6B80" tick={{ fill: '#6B6B80' }} tickFormatter={(value) => `${Number(value).toFixed(1)}s`} />
            <Tooltip
              contentStyle={{ background: '#111118', border: '1px solid #2A2A3D', borderRadius: 8 }}
              formatter={(value) => [`${Number(value).toFixed(3)}s`, 'Time']}
            />
            <Bar dataKey="d1" name={d1.abbreviation} fill="#1E90FF" radius={[4, 4, 0, 0]} />
            <Bar dataKey="d2" name={d2.abbreviation} fill="#FF8700" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-f1-muted md:grid-cols-4">
        {data.map((row) => (
          <div key={row.sector} className="rounded border border-f1-border px-2 py-1 text-center">
            {row.delta > 0 ? d2.abbreviation : d1.abbreviation} {formatGap(Math.abs(row.delta))}
          </div>
        ))}
      </div>
    </section>
  );
}
