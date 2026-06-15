import { formatMetricValue, metricTone, type ModelMetricMap } from './modelUtils';

interface MetricsDisplayProps {
  kind: 'regression' | 'classification';
  metrics: ModelMetricMap;
}

const metricLabels: Record<string, string> = {
  mae: 'MAE',
  rmse: 'RMSE',
  r2: 'R2',
  accuracy: 'Accuracy',
  precision: 'Precision',
  recall: 'Recall',
  f1: 'F1-Score',
  f1_score: 'F1-Score',
  roc_auc: 'ROC-AUC',
};

export function MetricsDisplay({ kind, metrics }: MetricsDisplayProps) {
  const keys = kind === 'regression' ? ['mae', 'rmse', 'r2'] : ['accuracy', 'precision', 'recall', metrics.f1_score !== undefined ? 'f1_score' : 'f1', 'roc_auc'];

  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-3">
      {keys.map((key) => (
        <div key={key} className="rounded border border-f1-border bg-f1-dark/40 p-3">
          <p className="text-[0.65rem] font-semibold uppercase tracking-widest text-f1-muted">{metricLabels[key]}</p>
          <p className={`mt-1 font-mono text-lg font-semibold ${metricTone(key, metrics[key])}`}>
            {formatMetricValue(key, metrics[key])}
          </p>
        </div>
      ))}
    </div>
  );
}
