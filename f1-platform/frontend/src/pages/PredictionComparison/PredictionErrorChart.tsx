import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { chartTooltipStyles } from '../../lib/chartTooltip';
import type { PredictionDriverComparison } from '../../types';

interface PredictionErrorChartProps {
  drivers: PredictionDriverComparison[];
}

function errorColor(error: number | null) {
  const value = Math.abs(error ?? 0);
  if (value <= 1) return '#48C774';
  if (value <= 3) return '#FFB000';
  return '#E8002D';
}

export function PredictionErrorChart({ drivers }: PredictionErrorChartProps) {
  const data = drivers
    .filter((driver) => driver.actual_rank !== null)
    .map((driver) => ({
      driver: driver.driver.abbreviation,
      driverName: driver.driver.full_name,
      team: driver.team.name,
      predicted: driver.predicted_rank,
      actual: driver.actual_rank,
      error: Math.abs(driver.position_error ?? 0),
    }));

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Predicted Rank vs Actual Rank</p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 24, bottom: 24, left: 4 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis type="number" dataKey="predicted" name="Predicted rank" domain={[1, 20]} stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <YAxis type="number" dataKey="actual" name="Actual rank" domain={[1, 20]} reversed stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <ZAxis type="number" dataKey="error" range={[90, 360]} />
            <ReferenceLine segment={[{ x: 1, y: 1 }, { x: 20, y: 20 }]} stroke="#6B6B80" strokeDasharray="4 4" />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              {...chartTooltipStyles}
              formatter={(value, name) => [Number(value).toFixed(1), name]}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.driverName || ''}
            />
            <Scatter data={data}>
              {data.map((entry) => (
                <Cell key={entry.driver} fill={errorColor(entry.error)} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
