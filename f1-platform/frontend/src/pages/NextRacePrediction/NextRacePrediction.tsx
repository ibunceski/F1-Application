import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Zap } from 'lucide-react';
import {
  generateNextRacePredictions,
  getNextRacePredictionContext,
  getNextRacePredictions,
} from '../../api/predictions';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { ApiError } from '../../lib/api';
import type { Prediction } from '../../types';
import { NextRaceActions } from './NextRaceActions';
import { NextRaceHeader } from './NextRaceHeader';
import { NextRacePredictionTable } from './NextRacePredictionTable';
import { PredictionContextPanel } from './PredictionContextPanel';

function isNotFound(error: unknown) {
  return (error as ApiError | undefined)?.status === 404;
}

function predictionsErrorMessage(error: unknown) {
  const apiError = error as ApiError | undefined;
  if (apiError?.status === 404) return '';
  if (apiError?.status === 503) return 'Models are not trained or loaded.';
  return apiError?.message || 'Predictions could not be loaded.';
}

export function NextRacePrediction() {
  const queryClient = useQueryClient();

  const context = useQuery({
    queryKey: ['next-race-prediction-context'],
    queryFn: getNextRacePredictionContext,
    retry: 1,
  });

  const predictions = useQuery({
    queryKey: ['next-race-predictions'],
    queryFn: getNextRacePredictions,
    retry: 1,
  });

  const generate = useMutation<Prediction[], Error, void>({
    mutationFn: () => generateNextRacePredictions('auto'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['next-race-predictions'] });
      queryClient.invalidateQueries({ queryKey: ['next-race-prediction-context'] });
    },
  });

  if (context.isLoading) return <LoadingSpinner />;
  if (context.isError) {
    const message = isNotFound(context.error) ? 'No next race found.' : 'Next race context could not be loaded.';
    return <ErrorState message={message} onRetry={() => context.refetch()} />;
  }
  if (!context.data) return <ErrorState message="Next race context could not be loaded." onRetry={() => context.refetch()} />;

  const predictionRows = predictions.data || generate.data || [];
  const hasPredictionLoadError = predictions.isError && !isNotFound(predictions.error);

  return (
    <div className="space-y-6">
      <NextRaceHeader race={context.data.race} daysUntilRace={context.data.days_until_race} />
      <PredictionContextPanel context={context.data} />
      <NextRaceActions predictions={predictionRows} mutation={generate} />

      {predictions.isLoading ? <LoadingSpinner /> : null}
      {hasPredictionLoadError ? (
        <ErrorState message={predictionsErrorMessage(predictions.error)} onRetry={() => predictions.refetch()} />
      ) : null}
      {!predictions.isLoading && !hasPredictionLoadError && !predictionRows.length ? (
        <EmptyState
          title="No next race predictions"
          description="Run the next race prediction set once models and features are ready."
          icon={Zap}
        />
      ) : null}
      {predictionRows.length ? <NextRacePredictionTable predictions={predictionRows} /> : null}
    </div>
  );
}
