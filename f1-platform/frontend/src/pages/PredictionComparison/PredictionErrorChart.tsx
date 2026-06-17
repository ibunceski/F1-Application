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
import type { PredictionDriverComparison } from '../../types';

interface PredictionErrorChartProps {
  drivers: PredictionDriverComparison[];
}

interface PredictionErrorDatum {
  driver: string;
  driverName: string;
  team: string;
  predicted: number;
  actual: number;
  error: number;
}

const errorLegend = [
  { label: 'Within 1 place', color: '#48C774' },
  { label: '2-3 places off', color: '#FFB000' },
  { label: '4+ places off', color: '#E8002D' },
];

function errorColor(error: number | null) {
  const value = Math.abs(error ?? 0);
  if (value <= 1) return '#48C774';
  if (value <= 3) return '#FFB000';
  return '#E8002D';
}

function PredictionErrorTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload?: PredictionErrorDatum }> }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;

  return (
    <div className="rounded-lg border border-f1-border bg-[#111118] px-3 py-2 text-sm text-f1-white shadow-xl">
      <p className="font-semibold text-f1-white">
        {row.driverName} ({row.driver})
      </p>
      <p className="mt-0.5 text-xs text-f1-muted">{row.team}</p>
      <div className="mt-3 space-y-1 text-f1-white">
        <p>Predicted rank: {row.predicted.toFixed(1)}</p>
        <p>Actual rank: {row.actual.toFixed(1)}</p>
        <p>Error: {row.error.toFixed(1)}</p>
      </div>
    </div>
  );
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
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="section-label">Predicted Rank vs Actual Rank</p>
          <p className="mt-1 text-xs text-f1-muted">Dots closer to the dashed diagonal line were predicted more accurately.</p>
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-f1-muted">
          {errorLegend.map((item) => (
            <span key={item.label} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 28, bottom: 36, left: 12 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis
              type="number"
              dataKey="predicted"
              name="Predicted rank"
              domain={[1, 20]}
              label={{ value: 'Predicted rank', position: 'insideBottom', offset: -24, fill: '#8A8AA0' }}
              stroke="#6B6B80"
              tick={{ fill: '#6B6B80' }}
            />
            <YAxis
              type="number"
              dataKey="actual"
              name="Actual rank"
              domain={[1, 20]}
              reversed
              label={{ value: 'Actual finish rank', angle: -90, position: 'insideLeft', fill: '#8A8AA0' }}
              stroke="#6B6B80"
              tick={{ fill: '#6B6B80' }}
            />
            <ZAxis type="number" dataKey="error" range={[90, 360]} />
            <ReferenceLine segment={[{ x: 1, y: 1 }, { x: 20, y: 20 }]} stroke="#6B6B80" strokeDasharray="4 4" />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              content={<PredictionErrorTooltip />}
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
