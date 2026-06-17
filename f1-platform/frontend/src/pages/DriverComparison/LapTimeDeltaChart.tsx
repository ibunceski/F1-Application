import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { chartTooltipStyles } from '../../lib/chartTooltip';
import { formatGap } from '../../lib/formatters';
import type { LapTime } from '../../types';

interface LapTimeDeltaChartProps {
  lapTimesD1: LapTime[];
  lapTimesD2: LapTime[];
  d1Name: string;
  d2Name: string;
}

function cleanByLap(laps: LapTime[]) {
  return new Map(
    laps
      .filter((lap) => lap.lap_time_ms !== null && !lap.deleted && !lap.is_pit_in_lap && !lap.is_pit_out_lap)
      .map((lap) => [lap.lap_number, lap.lap_time_ms as number]),
  );
}

export function LapTimeDeltaChart({ lapTimesD1, lapTimesD2, d1Name, d2Name }: LapTimeDeltaChartProps) {
  const d1 = cleanByLap(lapTimesD1);
  const d2 = cleanByLap(lapTimesD2);
  const data = [...d1.entries()]
    .filter(([lap]) => d2.has(lap))
    .map(([lap, time]) => ({
      lap,
      delta: time - Number(d2.get(lap)),
    }));

  return (
    <section className="card p-4">
      <div className="mb-4">
        <p className="section-label">Lap-by-Lap Delta</p>
        <p className="mt-1 text-xs text-f1-muted">Positive = {d1Name} was slower</p>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 24, bottom: 12, left: 8 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis dataKey="lap" stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <YAxis stroke="#6B6B80" tick={{ fill: '#6B6B80' }} tickFormatter={(value) => `${Number(value).toFixed(0)}ms`} />
            <ReferenceLine y={0} stroke="#E8E8F0" />
            <Tooltip
              {...chartTooltipStyles}
              formatter={(value) => [formatGap(Math.abs(Number(value))), Number(value) > 0 ? `${d2Name} faster` : `${d1Name} faster`]}
              labelFormatter={(label) => `Lap ${label}`}
            />
            <Bar dataKey="delta">
              {data.map((row) => (
                <Cell key={row.lap} fill={row.delta >= 0 ? '#1E90FF' : '#FF8700'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
