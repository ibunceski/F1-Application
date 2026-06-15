import { useQuery } from '@tanstack/react-query';
import { getFeatureImportances, getModelInfo } from '../../api/predictions';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { FeatureImportancePanel } from './FeatureImportancePanel';
import { ModelCard } from './ModelCard';
import { ModelPipelineDiagram } from './ModelPipelineDiagram';
import { getAlgorithm, getModelMetrics, mergeImportances, modelDefinitions } from './modelUtils';

export function ModelExplanation() {
  const info = useQuery({ queryKey: ['model-info'], queryFn: getModelInfo });
  const importances = useQuery({ queryKey: ['feature-importances'], queryFn: getFeatureImportances });

  if (info.isLoading || importances.isLoading) return <LoadingSpinner />;
  if (info.isError || importances.isError) return <ErrorState message="Model metadata could not be loaded." />;

  const featureImportances = mergeImportances(info.data, importances.data);

  return (
    <div className="space-y-8">
      <header className="border-b border-f1-border pb-5">
        <p className="section-label">Model Explanation</p>
        <h1 className="mt-2 text-3xl font-bold text-f1-white">Prediction Model - How It Works</h1>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-f1-muted">
          The platform combines historical timing data, race results, lap pace, weather, and circuit history into a set of pre-race features. Four
          trained models then estimate finishing position, points probability, podium probability, and likely position gain or loss.
        </p>
      </header>

      <ModelPipelineDiagram />

      <section className="space-y-4">
        <div className="flex items-end justify-between border-b border-f1-border pb-3">
          <div>
            <p className="section-label">Models</p>
            <h2 className="mt-1 text-xl font-bold text-f1-white">Evaluation Metrics</h2>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {modelDefinitions.map((definition) => (
            <ModelCard
              key={definition.key}
              modelName={definition.label}
              algorithm={getAlgorithm(info.data, definition)}
              targetVariable={definition.target}
              kind={definition.kind}
              metrics={getModelMetrics(info.data, definition.key)}
            />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div className="border-b border-f1-border pb-3">
          <p className="section-label">Feature Importance</p>
          <h2 className="mt-1 text-xl font-bold text-f1-white">Signals That Move Predictions</h2>
        </div>
        <FeatureImportancePanel importances={featureImportances} modelInfo={info.data} />
      </section>

      <section className="rounded-lg border border-amber-400/40 bg-amber-400/5 p-5">
        <h2 className="text-lg font-bold text-amber-200">Model Limitations &amp; Caveats</h2>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed text-f1-text">
          <li>Cannot predict safety cars, red flags, or race incidents</li>
          <li>Cannot account for in-race weather changes not present in qualifying</li>
          <li>Strategy changes during the race are not modeled</li>
          <li>New drivers with fewer than 5 races of history have less accurate predictions</li>
          <li>Wet races have higher uncertainty due to fewer historical examples</li>
          <li>This model is for analytical purposes only, not for betting guidance</li>
        </ul>
      </section>
    </div>
  );
}
