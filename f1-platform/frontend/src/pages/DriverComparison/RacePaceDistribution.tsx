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
  y: number;
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
    y,
    p10: percentile(values, 0.1),
    p25: percentile(values, 0.25),
    p50: percentile(values, 0.5),
    p75: percentile(values, 0.75),
    p90: percentile(values, 0.9),
  };
}

function BoxShape({ xAxis, yAxis, payload }: BoxShapeProps) {
  if (!payload || !xAxis || !yAxis) return null;
  const y = yAxis.scale(payload.y);
  const x10 = xAxis.scale(payload.p10);
  const x25 = xAxis.scale(payload.p25);
  const x50 = xAxis.scale(payload.p50);
  const x75 = xAxis.scale(payload.p75);
  const x90 = xAxis.scale(payload.p90);
  return (
    <g>
      <line x1={x10} x2={x90} y1={y} y2={y} stroke="#6B6B80" strokeWidth={2} />
      <rect x={x25} y={y - 12} width={x75 - x25} height={24} fill="#1A1A27" stroke="#E8002D" />
      <line x1={x50} x2={x50} y1={y - 16} y2={y + 16} stroke="#E8E8F0" strokeWidth={2} />
      <line x1={x10} x2={x10} y1={y - 8} y2={y + 8} stroke="#6B6B80" />
      <line x1={x90} x2={x90} y1={y - 8} y2={y + 8} stroke="#6B6B80" />
    </g>
  );
}

export function RacePaceDistribution({ lapTimesD1, lapTimesD2, d1Name, d2Name }: RacePaceDistributionProps) {
  const data = [box(d1Name, 2, lapTimesD1), box(d2Name, 1, lapTimesD2)];

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Race Pace Distribution</p>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 80 }}>
            <CartesianGrid stroke="#2A2A3D" horizontal={false} />
            <XAxis type="number" dataKey="p50" stroke="#6B6B80" tick={{ fill: '#6B6B80' }} tickFormatter={(value) => `${Number(value).toFixed(1)}s`} />
            <YAxis type="number" dataKey="y" domain={[0.5, 2.5]} ticks={[1, 2]} tickFormatter={(value) => (value === 2 ? d1Name : d2Name)} stroke="#6B6B80" tick={{ fill: '#E8E8F0' }} />
            <Scatter data={data} shape={<BoxShape />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
