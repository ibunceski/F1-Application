import type { UseMutationResult } from '@tanstack/react-query';
import { RefreshCw, Zap } from 'lucide-react';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { ApiError } from '../../lib/api';
import type { Prediction } from '../../types';

interface NextRaceActionsProps {
  predictions: Prediction[];
  mutation: UseMutationResult<Prediction[], Error, void, unknown>;
}

function errorMessage(error: Error | null) {
  if (!error) return '';
  const apiError = error as ApiError;
  if (apiError.status === 400) return error.message || 'Required race data is not available yet.';
  if (apiError.status === 404) return 'No next race was found.';
  if (apiError.status === 503) return 'Models are not trained or loaded.';
  return error.message || 'Prediction generation failed.';
}

export function NextRaceActions({ predictions, mutation }: NextRaceActionsProps) {
  const hasPredictions = predictions.length > 0;
  const modelVersion = predictions[0]?.model_version;

  return (
    <section className="card-elevated p-5">
      {mutation.isPending ? (
        <div className="flex items-center gap-4">
          <LoadingSpinner />
          <div>
            <p className="font-semibold text-f1-white">Generating next race predictions...</p>
            <p className="text-sm text-f1-muted">Using the recommended context and refreshing the prediction table.</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="section-label">Prediction Status</p>
            <p className="mt-2 text-lg font-semibold text-f1-white">
              {hasPredictions ? 'Predictions available' : 'No predictions generated yet'}
            </p>
            <p className="mt-1 text-sm text-f1-muted">
              {hasPredictions ? `Model version ${modelVersion}` : 'Generate the full next race prediction set for every driver.'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-f1-red px-5 py-3 text-sm font-bold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60 lg:w-64"
            disabled={mutation.isPending}
          >
            {hasPredictions ? <RefreshCw className="h-4 w-4" /> : <Zap className="h-4 w-4" />}
            Predict Next Race
          </button>
        </div>
      )}
      {mutation.isError ? (
        <div className="mt-4">
          <ErrorState message={errorMessage(mutation.error)} />
        </div>
      ) : null}
    </section>
  );
}
