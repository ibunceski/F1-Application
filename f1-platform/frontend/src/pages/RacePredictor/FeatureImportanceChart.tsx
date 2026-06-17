import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { chartTooltipStyles } from '../../lib/chartTooltip';

interface FeatureImportanceChartProps {
  importances: Record<string, number>;
  modelName: string;
}

const featureLabels: Record<string, string> = {
  grid_position: 'Grid Position',
  qualifying_position: 'Qualifying Position',
  gap_to_pole_ms: 'Gap to Pole (ms)',
  avg_race_pace_ms: 'Avg Race Pace (ms)',
  driver_recent_form: 'Driver Recent Form',
  team_recent_form: 'Team Recent Form',
  circuit_history_avg_finish: 'Circuit History',
  circuit_history_dnf_rate: 'Circuit DNF Rate',
  dnf_rate_recent: 'Recent DNF Rate',
  weather_is_wet: 'Wet Race',
  avg_track_temp_c: 'Track Temperature',
};

function humanize(feature: string) {
  return featureLabels[feature] || feature.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());
}

export function FeatureImportanceChart({ importances, modelName }: FeatureImportanceChartProps) {
  const data = Object.entries(importances)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([feature, value]) => ({ feature: humanize(feature), value }));

  return (
    <section className="card p-4">
      <p className="section-label mb-4">Feature Importance — {modelName} Model</p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 86 }}>
            <CartesianGrid stroke="#2A2A3D" horizontal={false} />
            <XAxis type="number" domain={[0, 'dataMax']} stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <YAxis type="category" dataKey="feature" width={140} stroke="#6B6B80" tick={{ fill: '#E8E8F0', fontSize: 11 }} />
            <Tooltip
              {...chartTooltipStyles}
              formatter={(value) => [Number(value).toFixed(4), 'Importance']}
            />
            <Bar dataKey="value" fill="#E8002D" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
