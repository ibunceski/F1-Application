import { apiClient } from '../lib/api';
import type {
  FeatureImportances,
  ModelInfo,
  NextRacePredictionContext,
  NextRacePredictionMode,
  Prediction,
  PredictionComparison,
  PredictionComparisonContext,
  PredictionContext,
} from '../types';

export async function generatePredictions(raceId: number, force = false, context: PredictionContext = 'post_qualifying'): Promise<Prediction[]> {
  const { data } = await apiClient.post<Prediction[]>(`/predictions/races/${raceId}/generate`, {
    force_regenerate: force,
    prediction_context: context,
  });
  return data;
}

export async function getPredictions(raceId: number, context: PredictionContext = 'post_qualifying'): Promise<Prediction[]> {
  const { data } = await apiClient.get<Prediction[]>(`/predictions/races/${raceId}`, {
    params: { prediction_context: context },
  });
  return data;
}

export async function getFeatureImportances(): Promise<FeatureImportances> {
  const { data } = await apiClient.get<FeatureImportances>('/predictions/feature-importances');
  return data;
}

export async function getModelInfo(): Promise<ModelInfo> {
  const { data } = await apiClient.get<ModelInfo>('/predictions/model-info');
  return data;
}

export async function getNextRacePredictionContext(): Promise<NextRacePredictionContext> {
  const { data } = await apiClient.get<NextRacePredictionContext>('/predictions/next-race/context');
  return data;
}

export async function getNextRacePredictions(): Promise<Prediction[]> {
  const { data } = await apiClient.get<Prediction[]>('/predictions/next-race');
  return data;
}

export async function generateNextRacePredictions(
  context: NextRacePredictionMode = 'auto',
  forceRegenerate = false,
): Promise<Prediction[]> {
  const { data } = await apiClient.post<Prediction[]>('/predictions/next-race/generate', {
    context,
    force_regenerate: forceRegenerate,
  });
  return data;
}

export async function getPredictionComparison(
  raceId: number,
  context: PredictionComparisonContext = 'latest',
): Promise<PredictionComparison> {
  const { data } = await apiClient.get<PredictionComparison>(`/predictions/races/${raceId}/comparison`, {
    params: { context },
  });
  return data;
}
