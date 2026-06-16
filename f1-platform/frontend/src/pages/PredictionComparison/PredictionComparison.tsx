import { useQuery } from '@tanstack/react-query';
import { WandSparkles } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { getPredictionComparison } from '../../api/predictions';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { ApiError } from '../../lib/api';
import { formatDate } from '../../lib/formatters';
import type { PredictionContext } from '../../types';
import { PredictionAccuracySummary } from './PredictionAccuracySummary';
import { PredictionComparisonTable } from './PredictionComparisonTable';
import { PredictionErrorChart } from './PredictionErrorChart';

function contextLabel(context: PredictionContext) {
  return context === 'post_qualifying' ? 'Post-Qualifying' : 'Pre-Qualifying';
}

function isApiStatus(error: unknown, status: number) {
  return (error as ApiError | undefined)?.status === status;
}

export function PredictionComparison() {
  const params = useParams();
  const year = Number(params.year || 2024);
  const raceId = Number(params.raceId);

  const comparison = useQuery({
    queryKey: ['prediction-comparison', raceId, 'latest'],
    queryFn: () => getPredictionComparison(raceId, 'latest'),
    enabled: Boolean(raceId),
    retry: 1,
  });

  if (comparison.isLoading) return <LoadingSpinner />;

  if (comparison.isError) {
    if (isApiStatus(comparison.error, 400)) {
      return <EmptyState title="Actual race results are not available yet." description="Prediction accuracy will appear after final race results are ingested." />;
    }

    if (isApiStatus(comparison.error, 404)) {
      return (
        <div className="space-y-4">
          <EmptyState title="Generate prediction first" description="Predictions have not been generated for this race yet." icon={WandSparkles} />
          <Link
            to={`/seasons/${year}/races/${raceId}/predict`}
            className="inline-flex rounded-md bg-f1-red px-4 py-2 text-sm font-bold text-white hover:bg-red-700"
          >
            Generate prediction first
          </Link>
        </div>
      );
    }

    return <ErrorState message="Prediction comparison could not be loaded." onRetry={() => comparison.refetch()} />;
  }

  if (!comparison.data) {
    return <ErrorState message="Prediction comparison could not be loaded." onRetry={() => comparison.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2 border-b border-f1-border pb-4">
        <p className="font-mono text-xs font-semibold uppercase tracking-widest text-f1-red">
          Round {comparison.data.race.round_number} - {comparison.data.race.circuit_name}
        </p>
        <h1 className="text-3xl font-bold text-f1-white">{comparison.data.race.race_name} Prediction Accuracy</h1>
        <p className="text-sm text-f1-muted">
          {formatDate(comparison.data.race.race_date)} - {contextLabel(comparison.data.context)} model - Version{' '}
          {comparison.data.model_version}
        </p>
      </header>

      <PredictionAccuracySummary summary={comparison.data.summary} />
      <PredictionErrorChart drivers={comparison.data.drivers} />
      <PredictionComparisonTable drivers={comparison.data.drivers} />
    </div>
  );
}
