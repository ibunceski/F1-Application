import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart3, Info } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getRaceById, getRaceQualifying, getRaceResults, getRacesBySeason } from '../../api/races';
import { generatePredictions, getFeatureImportances, getPredictions } from '../../api/predictions';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { NextRacePredictionMode, Prediction, PredictionContext } from '../../types';
import { FeatureImportanceChart } from './FeatureImportanceChart';
import { GeneratePredictionPanel } from './GeneratePredictionPanel';
import { PredictionContextSelector } from './PredictionContextSelector';
import { PredictionCharts } from './PredictionCharts';
import { PredictionTable } from './PredictionTable';

function positionImportancesForContext(data: unknown, context: PredictionContext): Record<string, number> {
  if (!data || typeof data !== 'object') return {};
  const record = data as Record<string, Record<string, number> | number>;
  const contextData = record[context];
  if (contextData && typeof contextData === 'object' && 'position_model' in contextData) {
    return (contextData as unknown as Record<string, Record<string, number>>).position_model || {};
  }
  const flatData = record.position_model;
  return flatData && typeof flatData === 'object' ? flatData : {};
}

function formatHeaderDate(value?: string) {
  if (!value) return '--';
  return new Intl.DateTimeFormat('en', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value));
}

function RaceSelectorFallback({ year }: { year: number }) {
  const races = useQuery({ queryKey: ['races', year], queryFn: () => getRacesBySeason(year) });
  if (races.isLoading) return <LoadingSpinner />;
  if (races.isError) return <ErrorState message="Races could not be loaded." />;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-f1-white">Select Race</h1>
      <div className="grid gap-3">
        {races.data?.map((race) => (
          <Link key={race.id} to={`/seasons/${year}/races/${race.id}/predict`} className="card grid grid-cols-[64px_1fr_auto] items-center gap-4 p-4 hover:border-f1-red">
            <span className="data-value">R{race.round_number}</span>
            <div>
              <p className="font-semibold text-f1-white">{race.race_name}</p>
              <p className="text-sm text-f1-muted">{race.circuit_name}</p>
            </div>
            <span className="rounded border border-f1-border px-3 py-1 text-xs">Predict</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function RacePredictor() {
  const params = useParams();
  const year = Number(params.year || 2024);
  const raceId = params.raceId ? Number(params.raceId) : undefined;
  const queryClient = useQueryClient();
  const [selectedContext, setSelectedContext] = useState<NextRacePredictionMode>('auto');

  const race = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRaceById(raceId as number),
    enabled: Boolean(raceId),
  });
  const qualifying = useQuery({
    queryKey: ['qualifying', raceId],
    queryFn: () => getRaceQualifying(raceId as number),
    enabled: Boolean(raceId),
  });
  const results = useQuery({
    queryKey: ['race-results', raceId],
    queryFn: () => getRaceResults(raceId as number),
    enabled: Boolean(raceId),
    retry: 1,
  });

  const qualifyingAvailable = Boolean(qualifying.data?.length);
  const effectiveContext: PredictionContext = selectedContext === 'auto'
    ? qualifyingAvailable ? 'post_qualifying' : 'pre_qualifying'
    : selectedContext;
  const contextReady = selectedContext !== 'auto' || !qualifying.isLoading;

  const predictions = useQuery({
    queryKey: ['predictions', raceId, effectiveContext],
    queryFn: () => getPredictions(raceId as number, effectiveContext),
    enabled: Boolean(raceId) && contextReady,
    retry: 1,
  });
  const featureImportances = useQuery({
    queryKey: ['feature-importances'],
    queryFn: getFeatureImportances,
  });

  const generate = useMutation<Prediction[], Error, boolean>({
    mutationFn: (force) => generatePredictions(raceId as number, force, effectiveContext),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['predictions', raceId, effectiveContext] }),
  });

  if (!raceId) return <RaceSelectorFallback year={year} />;
  if (race.isLoading) return <LoadingSpinner />;
  if (race.isError) return <ErrorState message="Race information could not be loaded." />;

  const predictionRows = predictions.data || generate.data?.filter((prediction) => prediction.model_context === effectiveContext) || [];
  const positionImportances = positionImportancesForContext(featureImportances.data, effectiveContext);
  const hasRaceResults = Boolean(results.data?.length);
  const raceDate = race.data?.race_date ? new Date(race.data.race_date) : null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const isFutureRace = raceDate ? raceDate >= today : false;
  const invalidPostQualifying = selectedContext === 'post_qualifying' && !qualifyingAvailable && !qualifying.isLoading;
  const contextError = invalidPostQualifying
    ? 'Qualifying data is not available for this race. Use pre-qualifying mode.'
    : null;
  const generateButtonLabel = isFutureRace ? 'Predict Upcoming Race' : 'Generate Prediction';

  return (
    <div className="space-y-6">
      <header className="space-y-2 border-b border-f1-border pb-4">
        <p className="font-mono text-xs font-semibold uppercase tracking-widest text-f1-red">
          Round {race.data?.round_number} · {race.data?.circuit_name} · {formatHeaderDate(race.data?.race_date)}
        </p>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="text-3xl font-bold text-f1-white">{race.data?.race_name} Prediction</h1>
          {hasRaceResults ? (
            <Link
              to={`/seasons/${year}/races/${raceId}/prediction-comparison`}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-f1-border px-4 py-2 text-sm font-semibold text-f1-white hover:border-f1-red"
            >
              <BarChart3 className="h-4 w-4" />
              Compare Prediction vs Actual
            </Link>
          ) : null}
        </div>
      </header>

      <PredictionContextSelector
        selectedContext={selectedContext}
        effectiveContext={effectiveContext}
        isFutureRace={isFutureRace}
        qualifyingAvailable={qualifyingAvailable}
        resultsAvailable={hasRaceResults}
        onChange={setSelectedContext}
      />

      <GeneratePredictionPanel
        predictions={predictionRows}
        mutation={generate}
        modelContext={effectiveContext}
        buttonLabel={generateButtonLabel}
        disabled={Boolean(contextError)}
        validationError={contextError}
      />

      {predictions.isLoading ? <LoadingSpinner /> : null}
      {predictions.isError && !predictionRows.length ? (
        <EmptyState
          title="No predictions"
          description={
            effectiveContext === 'post_qualifying'
              ? 'Generate post-qualifying predictions once qualifying features are available.'
              : 'Generate pre-qualifying predictions from previous race weekends.'
          }
        />
      ) : null}

      {predictionRows.length ? (
        <>
          <PredictionTable predictions={predictionRows} qualifyingResults={qualifying.data || []} />
          <div className="rounded-lg border border-podium-bronze/50 bg-podium-bronze/10 p-4 text-sm text-f1-text">
            <div className="flex gap-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-podium-bronze" />
              <p>
                Predictions are based on historical qualifying pace, driver form, and circuit history. They cannot account
                for incidents, safety cars, or race strategy changes.
              </p>
            </div>
          </div>
          <PredictionCharts predictions={predictionRows} />
          <FeatureImportanceChart importances={positionImportances} modelName="Position" />
        </>
      ) : null}
    </div>
  );
}
