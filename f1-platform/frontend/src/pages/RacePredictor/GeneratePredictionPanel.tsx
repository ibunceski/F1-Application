import type { UseMutationResult } from '@tanstack/react-query';
import type { ApiError } from '../../lib/api';
import type { Prediction } from '../../types';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';

interface GeneratePredictionPanelProps {
  predictions: Prediction[];
  mutation: UseMutationResult<Prediction[], Error, boolean, unknown>;
}

function errorMessage(error: Error | null) {
  if (!error) return '';
  const apiError = error as ApiError;
  if (apiError.status === 400) return 'Features not available — run ingestion pipeline';
  if (apiError.status === 503) return 'Models are not loaded';
  return error.message || 'Prediction generation failed';
}

export function GeneratePredictionPanel({ predictions, mutation }: GeneratePredictionPanelProps) {
  const hasPredictions = predictions.length > 0;
  const modelVersion = predictions[0]?.model_version;

  return (
    <section className="card-elevated p-5">
      {mutation.isPending ? (
        <div className="flex items-center gap-4">
          <LoadingSpinner />
          <div>
            <p className="font-semibold text-f1-white">Generating predictions...</p>
            <p className="text-sm text-f1-muted">Running all race entries through the loaded model set.</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="section-label">Prediction Status</p>
            {hasPredictions ? (
              <>
                <p className="mt-2 text-lg font-semibold text-f1-white">Predictions available</p>
                <p className="mt-1 text-sm text-f1-muted">Model version {modelVersion}</p>
                {mutation.isSuccess ? (
                  <span className="mt-3 inline-flex rounded-full border border-compound-inter/40 px-3 py-1 text-xs font-semibold text-compound-inter">
                    Predictions generated at {new Date().toLocaleTimeString()}
                  </span>
                ) : null}
              </>
            ) : (
              <>
                <p className="mt-2 text-lg font-semibold text-f1-white">No prediction generated yet</p>
                <p className="mt-1 text-sm text-f1-muted">Generate the full race prediction set for every driver.</p>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => mutation.mutate(hasPredictions)}
            className={
              hasPredictions
                ? 'rounded-md border border-f1-border px-4 py-2 text-sm font-semibold text-f1-white hover:border-f1-red'
                : 'w-full rounded-md bg-f1-red px-5 py-3 text-sm font-bold text-white lg:w-80'
            }
          >
            {hasPredictions ? 'Regenerate' : 'Generate Prediction'}
          </button>
        </div>
      )}
      {mutation.isError ? <div className="mt-4"><ErrorState message={errorMessage(mutation.error)} /></div> : null}
    </section>
  );
}
