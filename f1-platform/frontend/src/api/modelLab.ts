import { apiClient } from '../lib/api';
import type {
  ModelLabAblations,
  ModelLabArtifacts,
  ModelLabContext,
  ModelLabExperimentList,
  ModelLabOverview,
  ModelLabResults,
  ModelLabTask,
} from '../types';

export async function getModelLabExperiments(): Promise<ModelLabExperimentList> {
  const { data } = await apiClient.get<ModelLabExperimentList>('/model-lab/experiments');
  return data;
}

export async function getModelLabOverview(experimentId?: string): Promise<ModelLabOverview> {
  const { data } = await apiClient.get<ModelLabOverview>('/model-lab/overview', { params: experimentId ? { experiment_id: experimentId } : undefined });
  return data;
}

export async function getModelLabResults(filters: {
  experimentId?: string;
  task?: ModelLabTask;
  context?: ModelLabContext;
  algorithm?: string;
  evaluationSeason?: number;
}): Promise<ModelLabResults> {
  const { experimentId, evaluationSeason, ...rest } = filters;
  const { data } = await apiClient.get<ModelLabResults>('/model-lab/results', {
    params: { ...rest, experiment_id: experimentId, evaluation_season: evaluationSeason },
  });
  return data;
}

export async function getModelLabAblations(filters: {
  experimentId?: string;
  task?: ModelLabTask;
  context?: ModelLabContext;
  algorithm?: string;
}): Promise<ModelLabAblations> {
  const { experimentId, ...rest } = filters;
  const { data } = await apiClient.get<ModelLabAblations>('/model-lab/ablations', { params: { ...rest, experiment_id: experimentId } });
  return data;
}

export async function getModelLabArtifacts(experimentId?: string): Promise<ModelLabArtifacts> {
  const { data } = await apiClient.get<ModelLabArtifacts>('/model-lab/artifacts', { params: experimentId ? { experiment_id: experimentId } : undefined });
  return data;
}
