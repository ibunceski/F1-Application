import { apiClient } from '../lib/api';
import type { FeatureImportances, ModelInfo, Prediction } from '../types';

export async function generatePredictions(raceId: number, force = false): Promise<Prediction[]> {
  const { data } = await apiClient.post<Prediction[]>(`/predictions/races/${raceId}/generate`, {
    force_regenerate: force,
  });
  return data;
}

export async function getPredictions(raceId: number): Promise<Prediction[]> {
  const { data } = await apiClient.get<Prediction[]>(`/predictions/races/${raceId}`);
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
