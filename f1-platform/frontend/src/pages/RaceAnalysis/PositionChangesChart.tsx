import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import type { PositionChange } from '../../types';

interface PositionChangesChartProps {
  positionChanges: PositionChange[];
}

export function PositionChangesChart({ positionChanges }: PositionChangesChartProps) {
  const data = [...positionChanges]
    .map((row) => ({
      driver: row.driver.abbreviation,
      change: row.position_change ?? 0,
    }))
    .sort((a, b) => b.change - a.change);

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Position Changes</p>
      <div className="h-96">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 8, right: 32, bottom: 8, left: 20 }}>
            <CartesianGrid stroke="#2A2A3D" horizontal={false} />
            <XAxis type="number" stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <YAxis type="category" dataKey="driver" width={50} stroke="#6B6B80" tick={{ fill: '#E8E8F0' }} />
            <Bar dataKey="change" radius={[4, 4, 4, 4]}>
              <LabelList dataKey="change" position="right" formatter={(value: number) => `${value > 0 ? '+' : ''}${value}`} fill="#E8E8F0" />
              {data.map((row) => (
                <Cell key={row.driver} fill={row.change >= 0 ? '#16a34a' : '#dc2626'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
