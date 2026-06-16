import { CheckCircle2, CircleX } from 'lucide-react';

interface PredictionOutcomeBadgesProps {
  winnerCorrect?: boolean;
  predictedPodium?: boolean;
  actualPodium?: boolean;
  predictedTop10?: boolean;
  actualTop10?: boolean;
  compact?: boolean;
}

function Badge({ tone, label }: { tone: 'good' | 'bad' | 'neutral'; label: string }) {
  const className =
    tone === 'good'
      ? 'border-compound-inter/40 text-compound-inter'
      : tone === 'bad'
        ? 'border-f1-red/50 text-f1-red'
        : 'border-f1-border text-f1-muted';
  const Icon = tone === 'bad' ? CircleX : CheckCircle2;

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${className}`}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

export function PredictionOutcomeBadges({
  winnerCorrect,
  predictedPodium,
  actualPodium,
  predictedTop10,
  actualTop10,
  compact = false,
}: PredictionOutcomeBadgesProps) {
  const badges = [];

  if (winnerCorrect !== undefined) {
    badges.push(<Badge key="winner" tone={winnerCorrect ? 'good' : 'bad'} label={winnerCorrect ? 'Correct winner' : 'Missed winner'} />);
  }
  if (predictedPodium !== undefined && actualPodium !== undefined) {
    const hit = predictedPodium && actualPodium;
    badges.push(<Badge key="podium" tone={hit ? 'good' : 'neutral'} label={hit ? 'Podium hit' : 'Podium miss'} />);
  }
  if (predictedTop10 !== undefined && actualTop10 !== undefined) {
    const hit = predictedTop10 && actualTop10;
    badges.push(<Badge key="top10" tone={hit ? 'good' : 'neutral'} label={hit ? 'Top 10 hit' : 'Top 10 miss'} />);
  }

  return <div className={`flex flex-wrap ${compact ? 'gap-1.5' : 'gap-2'}`}>{badges}</div>;
}
