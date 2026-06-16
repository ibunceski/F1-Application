import { CheckCircle2, Info, TimerReset } from 'lucide-react';
import type { NextRacePredictionContext, PredictionContext } from '../../types';

interface PredictionContextPanelProps {
  context: NextRacePredictionContext;
}

function contextTitle(context: PredictionContext) {
  return context === 'post_qualifying' ? 'Post-Qualifying Prediction' : 'Pre-Qualifying Prediction';
}

function explanation(context: PredictionContext) {
  if (context === 'post_qualifying') {
    return 'Prediction also includes qualifying/grid information.';
  }
  return "Prediction is based on previous weekends' results, pace, reliability, team form, and circuit history.";
}

export function PredictionContextPanel({ context }: PredictionContextPanelProps) {
  const isPostQualifying = context.recommended_context === 'post_qualifying';

  return (
    <section className="card-elevated p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="section-label">Prediction Context</p>
          <div className="mt-2 flex items-center gap-3">
            {isPostQualifying ? (
              <CheckCircle2 className="h-5 w-5 text-compound-inter" />
            ) : (
              <TimerReset className="h-5 w-5 text-podium-bronze" />
            )}
            <h2 className="text-xl font-semibold text-f1-white">{contextTitle(context.recommended_context)}</h2>
          </div>
          <p className="mt-3 max-w-3xl text-sm text-f1-muted">{explanation(context.recommended_context)}</p>
        </div>
        <div
          className={
            context.qualifying_available
              ? 'rounded-full border border-compound-inter/40 px-3 py-1 text-xs font-semibold text-compound-inter'
              : 'rounded-full border border-podium-bronze/50 px-3 py-1 text-xs font-semibold text-podium-bronze'
          }
        >
          {context.qualifying_available
            ? 'Qualifying data available - using post-qualifying model'
            : 'Using previous race weekends only'}
        </div>
      </div>
      <div className="mt-4 flex gap-3 rounded-md border border-f1-border bg-f1-surface/60 p-3 text-sm text-f1-text">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-f1-red" />
        <p>
          The selected model context is based on the next race state in the database and whether qualifying data is available.
        </p>
      </div>
    </section>
  );
}
