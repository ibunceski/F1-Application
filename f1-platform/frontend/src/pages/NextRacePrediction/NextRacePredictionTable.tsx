import { useMemo, useState } from 'react';
import { PositionBadge } from '../../components/ui/PositionBadge';
import type { Prediction } from '../../types';
import { teamColor } from '../RacePredictor/teamColors';

type SortKey =
  | 'predicted_rank'
  | 'driver'
  | 'team'
  | 'predicted_position'
  | 'top10_probability'
  | 'podium_probability'
  | 'winner_probability'
  | 'confidence_score'
  | 'model_context';

interface NextRacePredictionTableProps {
  predictions: Prediction[];
}

function probability(value: number | null) {
  return Math.max(0, Math.min(100, (value || 0) * 100));
}

function percent(value: number | null) {
  return `${probability(value).toFixed(1)}%`;
}

function contextLabel(value?: string) {
  if (value === 'post_qualifying') return 'Post-Qualifying';
  if (value === 'pre_qualifying') return 'Pre-Qualifying';
  return '--';
}

function ProgressBar({ value }: { value: number | null }) {
  const width = probability(value);
  return (
    <div className="flex min-w-28 items-center gap-2">
      <div className="h-1.5 w-full rounded-full bg-f1-border">
        <div className="h-1.5 rounded-full bg-f1-red" style={{ width: `${width}%` }} />
      </div>
      <span className="data-value w-12 text-right text-xs">{percent(value)}</span>
    </div>
  );
}

function rowClass(rank: number) {
  if (rank === 1) return 'border-l-2 border-podium-gold bg-podium-gold/5';
  if (rank === 2) return 'border-l-2 border-podium-silver bg-podium-silver/5';
  if (rank === 3) return 'border-l-2 border-podium-bronze bg-podium-bronze/5';
  return 'border-l-2 border-transparent';
}

export function NextRacePredictionTable({ predictions }: NextRacePredictionTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('predicted_rank');
  const [direction, setDirection] = useState<'asc' | 'desc'>('asc');

  const sorted = useMemo(() => {
    return [...predictions].sort((a, b) => {
      const values: Record<SortKey, [string | number, string | number]> = {
        predicted_rank: [a.predicted_rank, b.predicted_rank],
        driver: [a.driver.full_name, b.driver.full_name],
        team: [a.team.name, b.team.name],
        predicted_position: [a.predicted_position ?? 99, b.predicted_position ?? 99],
        top10_probability: [a.top10_probability ?? 0, b.top10_probability ?? 0],
        podium_probability: [a.podium_probability ?? 0, b.podium_probability ?? 0],
        winner_probability: [a.winner_probability ?? 0, b.winner_probability ?? 0],
        confidence_score: [a.confidence_score ?? 0, b.confidence_score ?? 0],
        model_context: [a.model_context ?? '', b.model_context ?? ''],
      };
      const [left, right] = values[sortKey];
      const comparison = typeof left === 'string' ? left.localeCompare(String(right)) : Number(left) - Number(right);
      return direction === 'asc' ? comparison : -comparison;
    });
  }, [direction, predictions, sortKey]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setDirection((value) => (value === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setDirection('asc');
  }

  const headers: [SortKey, string][] = [
    ['predicted_rank', 'Predicted Rank'],
    ['driver', 'Driver'],
    ['team', 'Team'],
    ['predicted_position', 'Predicted Finish'],
    ['top10_probability', 'Top 10'],
    ['podium_probability', 'Podium'],
    ['winner_probability', 'Win'],
    ['confidence_score', 'Confidence'],
    ['model_context', 'Model Context'],
  ];

  return (
    <section className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1120px] text-left text-sm">
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
            {sorted.map((prediction) => (
              <tr key={prediction.id} className={rowClass(prediction.predicted_rank)}>
                <td className="px-4 py-4">
                  <PositionBadge position={prediction.predicted_rank} />
                </td>
                <td className="px-4 py-4">
                  <p className="font-semibold text-f1-white">{prediction.driver.full_name}</p>
                  <p className="text-xs text-f1-muted">{prediction.driver.abbreviation}</p>
                </td>
                <td className="px-4 py-4">
                  <span className="border-l-4 pl-3 text-f1-text" style={{ borderColor: teamColor(prediction.team.name) }}>
                    {prediction.team.short_name || prediction.team.name}
                  </span>
                </td>
                <td className="data-value px-4 py-4">{prediction.predicted_position?.toFixed(1) ?? '--'}</td>
                <td className="px-4 py-4">
                  <ProgressBar value={prediction.top10_probability} />
                </td>
                <td className="px-4 py-4">
                  <ProgressBar value={prediction.podium_probability} />
                </td>
                <td className="px-4 py-4">
                  <ProgressBar value={prediction.winner_probability} />
                </td>
                <td className="data-value px-4 py-4">{percent(prediction.confidence_score)}</td>
                <td className="px-4 py-4">
                  <span className="rounded-full border border-f1-border px-3 py-1 text-xs font-semibold text-f1-text">
                    {contextLabel(prediction.model_context)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
