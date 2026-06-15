import { useMemo, useState } from 'react';
import type { Prediction, QualifyingResult } from '../../types';
import { teamColor } from './teamColors';

type SortKey =
  | 'predicted_rank'
  | 'driver'
  | 'team'
  | 'grid'
  | 'predicted_position'
  | 'predicted_position_gain'
  | 'podium_probability'
  | 'top10_probability'
  | 'winner_probability';

interface PredictionTableProps {
  predictions: Prediction[];
  qualifyingResults: QualifyingResult[];
}

function probability(value: number | null) {
  return Math.max(0, Math.min(100, (value || 0) * 100));
}

function ProgressBar({ value }: { value: number | null }) {
  const percent = probability(value);
  return (
    <div className="flex min-w-28 items-center gap-2">
      <div className="h-1.5 w-full rounded-full bg-f1-border">
        <div className="h-1.5 rounded-full bg-f1-red" style={{ width: `${percent}%` }} />
      </div>
      <span className="data-value w-12 text-right text-xs">{percent.toFixed(1)}%</span>
    </div>
  );
}

function deltaClass(value: number | null) {
  if (!value) return 'text-f1-muted';
  return value > 0 ? 'text-compound-inter' : 'text-f1-red';
}

function rowClass(rank: number, predictedPosition: number | null) {
  if ((predictedPosition || 0) > 20) return 'opacity-45';
  if (rank === 1) return 'border-l-2 border-podium-gold bg-podium-gold/5';
  if (rank === 2) return 'border-l-2 border-podium-silver bg-podium-silver/5';
  if (rank === 3) return 'border-l-2 border-podium-bronze bg-podium-bronze/5';
  return 'border-l-2 border-transparent';
}

export function PredictionTable({ predictions, qualifyingResults }: PredictionTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('predicted_rank');
  const [direction, setDirection] = useState<'asc' | 'desc'>('asc');
  const qualifyingByDriver = useMemo(
    () => new Map(qualifyingResults.map((result) => [result.driver_id, result])),
    [qualifyingResults],
  );

  const sorted = useMemo(() => {
    return [...predictions].sort((a, b) => {
      const values: Record<SortKey, [string | number, string | number]> = {
        predicted_rank: [a.predicted_rank, b.predicted_rank],
        driver: [a.driver.full_name, b.driver.full_name],
        team: [a.team.name, b.team.name],
        grid: [qualifyingByDriver.get(a.driver_id)?.position ?? 99, qualifyingByDriver.get(b.driver_id)?.position ?? 99],
        predicted_position: [a.predicted_position ?? 99, b.predicted_position ?? 99],
        predicted_position_gain: [a.predicted_position_gain ?? 0, b.predicted_position_gain ?? 0],
        podium_probability: [a.podium_probability ?? 0, b.podium_probability ?? 0],
        top10_probability: [a.top10_probability ?? 0, b.top10_probability ?? 0],
        winner_probability: [a.winner_probability ?? 0, b.winner_probability ?? 0],
      };
      const [left, right] = values[sortKey];
      const comparison = typeof left === 'string' ? left.localeCompare(String(right)) : Number(left) - Number(right);
      return direction === 'asc' ? comparison : -comparison;
    });
  }, [direction, predictions, qualifyingByDriver, sortKey]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setDirection((value) => (value === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setDirection('asc');
    }
  }

  const headers: [SortKey, string][] = [
    ['predicted_rank', 'Pred. Pos.'],
    ['driver', 'Driver'],
    ['team', 'Team'],
    ['grid', 'Grid'],
    ['predicted_position', 'Predicted Finish'],
    ['predicted_position_gain', 'Delta Position'],
    ['podium_probability', 'Podium %'],
    ['top10_probability', 'Top 10 %'],
    ['winner_probability', 'Win %'],
  ];

  return (
    <section className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <thead className="bg-f1-elevated text-xs uppercase text-f1-muted">
            <tr>
              {headers.map(([key, label]) => (
                <th key={key} className="px-4 py-3">
                  <button type="button" onClick={() => handleSort(key)} className="font-semibold hover:text-f1-white">
                    {label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-f1-border">
            {sorted.map((prediction) => {
              const qualifying = qualifyingByDriver.get(prediction.driver_id);
              const dnf = (prediction.predicted_position || 0) > 20;
              return (
                <tr key={prediction.id} className={rowClass(prediction.predicted_rank, prediction.predicted_position)}>
                  <td className="px-4 py-4">
                    <span className="data-value text-xl font-bold">{prediction.predicted_rank}</span>
                  </td>
                  <td className="px-4 py-4">
                    <p className="font-semibold text-f1-white">{prediction.driver.full_name}</p>
                    <p className="text-xs text-f1-muted">{prediction.team.name}</p>
                  </td>
                  <td className="px-4 py-4">
                    <span className="border-l-4 pl-3 text-f1-text" style={{ borderColor: teamColor(prediction.team.name) }}>
                      {prediction.team.short_name}
                    </span>
                  </td>
                  <td className="data-value px-4 py-4">{qualifying?.position ?? prediction.grid_position ?? '--'}</td>
                  <td className="data-value px-4 py-4">{dnf ? <span className="text-f1-red">DNF</span> : prediction.predicted_position?.toFixed(1)}</td>
                  <td className={`data-value px-4 py-4 ${deltaClass(prediction.predicted_position_gain)}`}>
                    {prediction.predicted_position_gain ? `${prediction.predicted_position_gain > 0 ? '+' : ''}${prediction.predicted_position_gain.toFixed(1)}` : '0.0'}
                  </td>
                  <td className="px-4 py-4"><ProgressBar value={prediction.podium_probability} /></td>
                  <td className="px-4 py-4"><ProgressBar value={prediction.top10_probability} /></td>
                  <td className="px-4 py-4"><ProgressBar value={prediction.winner_probability} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
