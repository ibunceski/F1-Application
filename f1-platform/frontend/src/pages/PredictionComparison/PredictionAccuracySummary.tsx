import { Award, Gauge, Target, Trophy } from 'lucide-react';
import type { PredictionComparisonSummary } from '../../types';
import { PredictionOutcomeBadges } from './PredictionOutcomeBadges';

interface PredictionAccuracySummaryProps {
  summary: PredictionComparisonSummary;
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export function PredictionAccuracySummary({ summary }: PredictionAccuracySummaryProps) {
  const cards = [
    { label: 'MAE', value: summary.mae.toFixed(2), icon: Gauge },
    { label: 'RMSE', value: summary.rmse.toFixed(2), icon: Target },
    { label: 'Top 10 accuracy', value: percent(summary.top10_accuracy), icon: Award },
    { label: 'Podium accuracy', value: percent(summary.podium_accuracy), icon: Trophy },
  ];

  return (
    <section className="grid gap-4 lg:grid-cols-[repeat(4,minmax(0,1fr))_260px]">
      {cards.map((card) => (
        <article key={card.label} className="card-elevated p-4">
          <div className="flex items-center gap-2 text-f1-muted">
            <card.icon className="h-4 w-4" />
            <p className="section-label">{card.label}</p>
          </div>
          <p className="data-value mt-3 text-2xl">{card.value}</p>
        </article>
      ))}
      <article className="card-elevated p-4">
        <p className="section-label mb-3">Winner</p>
        <PredictionOutcomeBadges winnerCorrect={summary.winner_correct} />
      </article>
    </section>
  );
}
