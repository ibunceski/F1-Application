import { MetricsDisplay } from './MetricsDisplay';
import type { ModelMetricMap } from './modelUtils';

interface ModelCardProps {
  modelName: string;
  algorithm: string;
  targetVariable: string;
  kind: 'regression' | 'classification';
  metrics: ModelMetricMap;
}

export function ModelCard({ modelName, algorithm, targetVariable, kind, metrics }: ModelCardProps) {
  return (
    <article className="card-elevated p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-f1-white">{modelName}</h3>
          <p className="mt-1 text-sm leading-relaxed text-f1-muted">Predicts: {targetVariable}</p>
        </div>
        <span className="rounded border border-f1-border px-3 py-1 font-mono text-xs text-f1-text">{algorithm}</span>
      </div>
      <MetricsDisplay kind={kind} metrics={metrics} />
    </article>
  );
}
