import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DriverTyreStrategy } from '../../types';
import { compoundColor } from './tyreUtils';

interface CompoundPaceChartProps {
  strategies: DriverTyreStrategy[];
}

function average(values: number[]) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

export function CompoundPaceChart({ strategies }: CompoundPaceChartProps) {
  const grouped = new Map<string, number[]>();
  strategies.forEach((strategy) => {
    strategy.stints.forEach((stint) => {
      if (stint.avg_lap_time_ms !== null) {
        const compound = stint.compound || 'UNKNOWN';
        grouped.set(compound, [...(grouped.get(compound) || []), stint.avg_lap_time_ms]);
      }
    });
  });
  const data = [...grouped.entries()]
    .map(([compound, values]) => ({ compound, pace: average(values) / 1000 }))
    .sort((a, b) => a.pace - b.pace);
  const fastest = data[0]?.pace ?? 0;

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Compound Pace</p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 24, bottom: 30, left: 8 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis dataKey="compound" stroke="#6B6B80" tick={{ fill: '#E8E8F0' }} />
            <YAxis stroke="#6B6B80" tick={{ fill: '#6B6B80' }} tickFormatter={(value) => `${Number(value).toFixed(1)}s`} />
            <Tooltip
              contentStyle={{ background: '#111118', border: '1px solid #2A2A3D', borderRadius: 8 }}
              formatter={(value) => [`${Number(value).toFixed(3)}s`, 'Average pace']}
            />
            <Bar dataKey="pace" radius={[4, 4, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.compound} fill={compoundColor(entry.compound)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-f1-muted">
        {data.map((entry) => (
          <span key={entry.compound} className="rounded border border-f1-border px-2 py-1">
            {entry.compound}: +{(entry.pace - fastest).toFixed(1)}s vs {data[0]?.compound}
          </span>
        ))}
      </div>
    </section>
  );
}
