import {
  Bar,
  BarChart,
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
import type { Prediction } from '../../types';
import { teamColor } from './teamColors';

interface PredictionChartsProps {
  predictions: Prediction[];
}

function scatterData(predictions: Prediction[]) {
  return predictions.map((prediction) => ({
    driver: prediction.driver.abbreviation,
    driverName: prediction.driver.full_name,
    team: prediction.team.name,
    grid: prediction.grid_position ?? 20,
    predicted: prediction.predicted_position ?? 20,
    winnerProbability: prediction.winner_probability ?? 0,
    gain: (prediction.predicted_position_gain ?? 0) > 0,
    modelContext: contextLabel(prediction.model_context),
  }));
}

function podiumData(predictions: Prediction[]) {
  return [...predictions]
    .sort((a, b) => a.predicted_rank - b.predicted_rank)
    .slice(0, 10)
    .map((prediction) => ({
      driver: prediction.driver.abbreviation,
      team: prediction.team.name,
      probability: prediction.podium_probability ?? 0,
      modelContext: contextLabel(prediction.model_context),
    }));
}

function contextLabel(value?: string) {
  if (value === 'post_qualifying') return 'Post-Qualifying';
  if (value === 'pre_qualifying') return 'Pre-Qualifying';
  return 'Model context unavailable';
}

export function PredictionCharts({ predictions }: PredictionChartsProps) {
  const scatter = scatterData(predictions);
  const podium = podiumData(predictions);

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="card p-4">
        <p className="section-label mb-4">Grid vs Predicted Finish</p>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 16, right: 20, bottom: 24, left: 4 }}>
              <CartesianGrid stroke="#2A2A3D" />
              <XAxis type="number" dataKey="grid" name="Grid" domain={[1, 20]} reversed={false} stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
              <YAxis type="number" dataKey="predicted" name="Predicted" domain={[1, 20]} reversed stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
              <ZAxis type="number" dataKey="winnerProbability" range={[80, 420]} />
              <ReferenceLine segment={[{ x: 1, y: 1 }, { x: 20, y: 20 }]} stroke="#6B6B80" strokeDasharray="4 4" />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{ background: '#111118', border: '1px solid #2A2A3D', borderRadius: 8 }}
                formatter={(value, name) => [Number(value).toFixed(1), name]}
                labelFormatter={(_, payload) => {
                  const row = payload?.[0]?.payload;
                  return row ? `${row.driverName} - ${row.modelContext}` : '';
                }}
              />
              <Scatter data={scatter}>
                {scatter.map((entry) => (
                  <Cell key={entry.driver} fill={entry.gain ? '#48C774' : '#E8002D'} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="card p-4">
        <p className="section-label mb-4">Podium Probability</p>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={podium} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 20 }}>
              <CartesianGrid stroke="#2A2A3D" horizontal={false} />
              <XAxis type="number" domain={[0, 1]} stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
              <YAxis type="category" dataKey="driver" width={54} stroke="#6B6B80" tick={{ fill: '#E8E8F0' }} />
              <Tooltip
                contentStyle={{ background: '#111118', border: '1px solid #2A2A3D', borderRadius: 8 }}
                formatter={(value) => [`${(Number(value) * 100).toFixed(1)}%`, 'Podium']}
                labelFormatter={(_, payload) => {
                  const row = payload?.[0]?.payload;
                  return row ? `${row.driver} - ${row.modelContext}` : '';
                }}
              />
              <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
                {podium.map((entry) => (
                  <Cell key={entry.driver} fill={teamColor(entry.team)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
