import { CheckCircle2, CircleAlert, Clock3 } from 'lucide-react';
import type { NextRacePredictionMode, PredictionContext } from '../../types';

interface PredictionContextSelectorProps {
  selectedContext: NextRacePredictionMode;
  effectiveContext: PredictionContext;
  isFutureRace: boolean;
  qualifyingAvailable: boolean;
  resultsAvailable: boolean;
  onChange: (context: NextRacePredictionMode) => void;
}

function contextLabel(context: PredictionContext) {
  return context === 'post_qualifying' ? 'Post-Qualifying' : 'Pre-Qualifying';
}

function contextDescription(context: PredictionContext) {
  if (context === 'post_qualifying') {
    return 'Uses previous race weekends plus qualifying and grid information for this race.';
  }
  return 'Uses previous race weekends only: form, pace, reliability, team strength, and circuit history.';
}

export function PredictionContextSelector({
  selectedContext,
  effectiveContext,
  isFutureRace,
  qualifyingAvailable,
  resultsAvailable,
  onChange,
}: PredictionContextSelectorProps) {
  const options: { value: NextRacePredictionMode; label: string }[] = [
    { value: 'auto', label: 'Auto' },
    { value: 'pre_qualifying', label: 'Pre-Qualifying' },
    { value: 'post_qualifying', label: 'Post-Qualifying' },
  ];

  return (
    <section className="card-elevated p-5">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="section-label">Prediction Context</p>
          <h2 className="mt-2 text-xl font-semibold text-f1-white">{contextLabel(effectiveContext)} model</h2>
          <p className="mt-2 max-w-3xl text-sm text-f1-muted">{contextDescription(effectiveContext)}</p>
        </div>
        <div className="flex w-full rounded-md border border-f1-border bg-f1-surface p-1 sm:w-auto">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              className={`flex-1 rounded px-3 py-2 text-sm font-semibold transition sm:flex-none ${
                selectedContext === option.value ? 'bg-f1-red text-white' : 'text-f1-muted hover:text-f1-white'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-md border border-f1-border bg-f1-surface/60 p-3">
          <div className="flex items-center gap-2 text-sm">
            <Clock3 className="h-4 w-4 text-f1-muted" />
            <span className="font-semibold text-f1-white">{isFutureRace ? 'Upcoming race' : 'Past race'}</span>
          </div>
          <p className="mt-1 text-xs text-f1-muted">
            {isFutureRace ? 'Auto mode will adapt as qualifying becomes available.' : 'Choose either pre- or post-qualifying mode.'}
          </p>
        </div>
        <div className="rounded-md border border-f1-border bg-f1-surface/60 p-3">
          <div className="flex items-center gap-2 text-sm">
            {qualifyingAvailable ? <CheckCircle2 className="h-4 w-4 text-compound-inter" /> : <CircleAlert className="h-4 w-4 text-podium-bronze" />}
            <span className="font-semibold text-f1-white">
              {qualifyingAvailable ? 'Qualifying available' : 'No qualifying data'}
            </span>
          </div>
          <p className="mt-1 text-xs text-f1-muted">
            {qualifyingAvailable ? 'Post-qualifying predictions can use current grid features.' : 'Use pre-qualifying mode for this race.'}
          </p>
        </div>
        <div className="rounded-md border border-f1-border bg-f1-surface/60 p-3">
          <div className="flex items-center gap-2 text-sm">
            {resultsAvailable ? <CheckCircle2 className="h-4 w-4 text-compound-inter" /> : <CircleAlert className="h-4 w-4 text-f1-muted" />}
            <span className="font-semibold text-f1-white">
              {resultsAvailable ? 'Actual results available' : 'No actual results yet'}
            </span>
          </div>
          <p className="mt-1 text-xs text-f1-muted">
            {resultsAvailable ? 'Prediction accuracy comparison is available.' : 'Comparison will appear after results are ingested.'}
          </p>
        </div>
      </div>
    </section>
  );
}
