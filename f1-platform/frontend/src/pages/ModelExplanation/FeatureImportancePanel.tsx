import { useMemo, useState } from 'react';
import type { FeatureImportances, ModelInfo } from '../../types';
import { formatDateTime, humanizeFeature, modelDefinitions } from './modelUtils';

interface FeatureImportancePanelProps {
  importances: FeatureImportances;
  modelInfo?: ModelInfo;
}

function explanationFor(features: string[]) {
  const [first, second, third] = features.map(humanizeFeature);
  if (!first) return 'Feature importance is unavailable for this model. Once models are trained, this panel will rank the signals that most influenced predictions.';

  return `${first} is the strongest predictor because it captures the clearest pre-race advantage in the available data. ${
    second || 'Historical pace'
  } adds context from recent performance, helping the model separate raw starting position from true race speed. ${
    third || 'Circuit history'
  } gives the prediction a circuit-specific correction, which matters because tyre wear, overtaking difficulty, and reliability vary by venue. These signals still cannot describe incidents or strategy calls that happen after lights out.`;
}

export function FeatureImportancePanel({ importances, modelInfo }: FeatureImportancePanelProps) {
  const availableModels = modelDefinitions.filter((definition) => importances[definition.key]);
  const [activeKey, setActiveKey] = useState(availableModels[0]?.key || modelDefinitions[0].key);
  const activeDefinition = modelDefinitions.find((definition) => definition.key === activeKey) || modelDefinitions[0];
  const rankedFeatures = useMemo(
    () => Object.entries(importances[activeKey] || {}).sort((a, b) => b[1] - a[1]).slice(0, 10),
    [activeKey, importances],
  );
  const maxImportance = Math.max(...rankedFeatures.map(([, value]) => value), 0);

  return (
    <section className="card p-5">
      <div className="flex flex-wrap gap-2 border-b border-f1-border pb-4">
        {modelDefinitions.map((definition) => (
          <button
            key={definition.key}
            type="button"
            onClick={() => setActiveKey(definition.key)}
            className={`rounded border px-3 py-2 text-sm font-semibold transition ${
              activeKey === definition.key
                ? 'border-f1-red bg-f1-elevated text-f1-white'
                : 'border-f1-border text-f1-muted hover:text-f1-white'
            }`}
          >
            {definition.shortLabel}
          </button>
        ))}
      </div>

      <div className="mt-5 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-3">
          {rankedFeatures.length ? (
            rankedFeatures.map(([feature, value], index) => (
              <div key={feature} className="grid grid-cols-[24px_180px_1fr_64px] items-center gap-3 text-sm">
                <span className="font-mono text-xs text-f1-muted">{index + 1}</span>
                <span className="text-f1-text">{humanizeFeature(feature)}</span>
                <div className="h-2 rounded-full bg-f1-border">
                  <div
                    className="h-2 rounded-full bg-f1-red"
                    style={{ width: `${maxImportance ? (value / maxImportance) * 100 : 0}%` }}
                  />
                </div>
                <span className="data-value text-right">{(value * 100).toFixed(1)}%</span>
              </div>
            ))
          ) : (
            <p className="rounded border border-f1-border bg-f1-elevated p-4 text-sm text-f1-muted">No feature importance data is available.</p>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <p className="section-label">Explanation</p>
            <p className="mt-2 text-sm leading-relaxed text-f1-text">{explanationFor(rankedFeatures.slice(0, 3).map(([feature]) => feature))}</p>
          </div>
          <div className="rounded border border-f1-border bg-f1-elevated p-4 text-sm leading-relaxed text-f1-muted">
            <p>
              Trained on{' '}
              <span className="text-f1-text">{modelInfo?.train_seasons?.join(', ') || '--'}</span> seasons.
            </p>
            <p>
              Validated on <span className="text-f1-text">{modelInfo?.test_season || '--'}</span> season.
            </p>
            <p>
              Model trained at <span className="text-f1-text">{formatDateTime(modelInfo?.trained_at)}</span>.
            </p>
            <p className="mt-2 text-xs text-f1-muted">
              Active model: <span className="text-f1-text">{activeDefinition.label}</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
