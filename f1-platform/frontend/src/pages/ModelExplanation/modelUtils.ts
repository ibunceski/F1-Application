import type { FeatureImportances, ModelInfo } from '../../types';

export interface ModelMetricMap {
  [key: string]: string | number | null | undefined;
}

export interface ModelDefinition {
  key: string;
  label: string;
  shortLabel: string;
  target: string;
  fallbackAlgorithm: string;
  kind: 'regression' | 'classification';
}

export const modelDefinitions: ModelDefinition[] = [
  {
    key: 'position_model',
    label: 'Finishing Position Model',
    shortLabel: 'Position Model',
    target: 'Final finishing position',
    fallbackAlgorithm: 'XGBoost Regressor',
    kind: 'regression',
  },
  {
    key: 'top10_model',
    label: 'Top 10 Finish Model',
    shortLabel: 'Top 10 Model',
    target: 'Probability of a points finish',
    fallbackAlgorithm: 'XGBoost Classifier',
    kind: 'classification',
  },
  {
    key: 'podium_model',
    label: 'Podium Finish Model',
    shortLabel: 'Podium Model',
    target: 'Probability of finishing in the top 3',
    fallbackAlgorithm: 'XGBoost Classifier',
    kind: 'classification',
  },
  {
    key: 'position_gain_model',
    label: 'Position Gain/Loss Model',
    shortLabel: 'Gain/Loss Model',
    target: 'Net positions gained or lost',
    fallbackAlgorithm: 'LightGBM Regressor',
    kind: 'regression',
  },
];

export const featureNameMap: Record<string, string> = {
  grid_position: 'Grid Position',
  qualifying_position: 'Qualifying Position',
  gap_to_pole_ms: 'Gap to Pole (ms)',
  avg_race_pace_ms: 'Avg Race Pace (ms)',
  driver_recent_form: 'Driver Recent Form',
  team_recent_form: 'Team Recent Form',
  circuit_history_avg_finish: 'Circuit History',
  circuit_history_dnf_rate: 'Circuit DNF Rate',
  dnf_rate_recent: 'Recent DNF Rate',
  weather_is_wet: 'Wet Race',
  avg_track_temp_c: 'Track Temperature',
};

export function humanizeFeature(feature: string) {
  return featureNameMap[feature] || feature.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());
}

export function getModelMetrics(info: ModelInfo | undefined, key: string): ModelMetricMap {
  return (info?.models?.[key] || {}) as ModelMetricMap;
}

export function getAlgorithm(info: ModelInfo | undefined, definition: ModelDefinition) {
  const metrics = getModelMetrics(info, definition.key);
  return String(metrics.algorithm || definition.fallbackAlgorithm);
}

export function mergeImportances(info: ModelInfo | undefined, importances: FeatureImportances | undefined): FeatureImportances {
  return importances && Object.keys(importances).length ? importances : info?.feature_importances || {};
}

export function formatDateTime(value?: string) {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatMetricValue(key: string, value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '--';
  if (typeof value === 'string') return value;
  if (['accuracy', 'precision', 'recall', 'f1', 'f1_score'].includes(key)) return `${(value * 100).toFixed(1)}%`;
  if (key === 'roc_auc') return value.toFixed(3);
  if (key === 'r2') return value.toFixed(2);
  if (key === 'mae' || key === 'rmse') return value.toFixed(2);
  return value.toFixed(2);
}

export function metricTone(key: string, value: string | number | null | undefined) {
  if (typeof value !== 'number') return 'text-f1-text';
  if (key === 'mae') return value < 3 ? 'text-green-400' : value < 5 ? 'text-amber-300' : 'text-red-400';
  if (key === 'rmse') return value < 4 ? 'text-green-400' : value < 6 ? 'text-amber-300' : 'text-red-400';
  if (key === 'r2') return value > 0.6 ? 'text-green-400' : value > 0.35 ? 'text-amber-300' : 'text-red-400';
  if (key === 'roc_auc') return value > 0.7 ? 'text-green-400' : value > 0.6 ? 'text-amber-300' : 'text-red-400';
  if (['accuracy', 'precision', 'recall', 'f1', 'f1_score'].includes(key)) {
    return value > 0.75 ? 'text-green-400' : value > 0.6 ? 'text-amber-300' : 'text-red-400';
  }
  return 'text-f1-text';
}
