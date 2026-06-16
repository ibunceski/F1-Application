import { CartesianGrid, ComposedChart, ResponsiveContainer, Scatter, XAxis, YAxis } from 'recharts';
import { cleanLapTimes } from './comparisonUtils';
import type { LapTime } from '../../types';

interface RacePaceDistributionProps {
  lapTimesD1: LapTime[];
  lapTimesD2: LapTime[];
  d1Name: string;
  d2Name: string;
}

interface PaceBox {
  driver: string;
  x: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
}

interface BoxShapeProps {
  yAxis?: { scale: (value: number) => number };
  xAxis?: { scale: (value: number) => number };
  payload?: PaceBox;
}

function percentile(values: number[], p: number) {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const index = (sorted.length - 1) * p;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

function box(driver: string, y: number, laps: LapTime[]): PaceBox {
  const values = cleanLapTimes(laps).map((value) => value / 1000);
  return {
    driver,
    x: y,
    p10: percentile(values, 0.1),
    p25: percentile(values, 0.25),
    p50: percentile(values, 0.5),
    p75: percentile(values, 0.75),
    p90: percentile(values, 0.9),
  };
}

function BoxShape({ xAxis, yAxis, payload }: BoxShapeProps) {
  if (!payload || !xAxis || !yAxis) return null;
  const x = xAxis.scale(payload.x);
  const y10 = yAxis.scale(payload.p10);
  const y25 = yAxis.scale(payload.p25);
  const y50 = yAxis.scale(payload.p50);
  const y75 = yAxis.scale(payload.p75);
  const y90 = yAxis.scale(payload.p90);
  return (
    <g>
      <line x1={x} x2={x} y1={y10} y2={y90} stroke="#6B6B80" strokeWidth={2} />
      <rect x={x - 18} y={y75} width={36} height={y25 - y75} fill="#1A1A27" stroke="#E8002D" />
      <line x1={x - 24} x2={x + 24} y1={y50} y2={y50} stroke="#E8E8F0" strokeWidth={2} />
      <line x1={x - 12} x2={x + 12} y1={y10} y2={y10} stroke="#6B6B80" />
      <line x1={x - 12} x2={x + 12} y1={y90} y2={y90} stroke="#6B6B80" />
    </g>
  );
}

export function RacePaceDistribution({ lapTimesD1, lapTimesD2, d1Name, d2Name }: RacePaceDistributionProps) {
  const data = [box(d1Name, 2, lapTimesD1), box(d2Name, 1, lapTimesD2)];

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Race Pace Distribution</p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 24, bottom: 12, left: 16 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis type="number" dataKey="x" domain={[0.5, 2.5]} ticks={[1, 2]} tickFormatter={(value) => (value === 2 ? d1Name : d2Name)} stroke="#6B6B80" tick={{ fill: '#E8E8F0' }} />
            <YAxis type="number" dataKey="p50" domain={['dataMin - 0.5', 'dataMax + 0.5']} stroke="#6B6B80" tick={{ fill: '#6B6B80' }} tickFormatter={(value) => `${Number(value).toFixed(1)}s`} />
            <Scatter data={data} shape={<BoxShape />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
