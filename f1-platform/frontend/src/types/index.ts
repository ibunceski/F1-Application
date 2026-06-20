export interface Season {
  id: number;
  year: number;
  total_races: number;
  champion_driver: string | null;
  champion_team: string | null;
  created_at: string;
}

export interface Race {
  id: number;
  season_id: number;
  round_number: number;
  circuit_name: string;
  circuit_location: string;
  circuit_country: string;
  race_name: string;
  race_date: string;
}

export interface Driver {
  id: number;
  driver_id: string;
  driver_number: number;
  full_name: string;
  abbreviation: string;
  nationality: string | null;
  team_id: number | null;
}

export interface Team {
  id: number;
  name: string;
  short_name: string;
  nationality: string | null;
  constructor_id: string;
}

export interface QualifyingResult {
  id: number;
  driver_id: number;
  team_id: number;
  position: number | null;
  q1_time_ms: number | null;
  q2_time_ms: number | null;
  q3_time_ms: number | null;
  best_time_ms: number | null;
  gap_to_pole_ms: number | null;
  driver: Driver;
  team: Team;
}

export interface RaceResult {
  id: number;
  driver_id: number;
  team_id: number;
  grid_position: number | null;
  finishing_position: number | null;
  classified_position: string | null;
  status: string;
  points: number;
  sprint_points: number;
  laps_completed: number;
  fastest_lap: boolean;
  fastest_lap_time_ms: number | null;
  driver: Driver;
  team: Team;
}

export interface LapTime {
  id: number;
  lap_number: number;
  lap_time_ms: number | null;
  sector1_ms: number | null;
  sector2_ms: number | null;
  sector3_ms: number | null;
  compound: TyreCompound | string | null;
  tyre_age_laps: number | null;
  stint_number: number | null;
  is_pit_out_lap: boolean;
  is_pit_in_lap: boolean;
  is_personal_best: boolean;
  deleted: boolean;
}

export type TyreCompound = 'SOFT' | 'MEDIUM' | 'HARD' | 'INTERMEDIATE' | 'WET';

export interface LapTimesByDriver {
  driver_id: number;
  driver_name: string;
  abbreviation: string;
  team_name: string | null;
  laps: LapTime[];
}

export interface TyreStint {
  compound: TyreCompound | string | null;
  stint_number: number | null;
  start_lap: number;
  end_lap: number;
  laps_on_tyre: number;
  avg_lap_time_ms: number | null;
}

export interface DriverTyreStrategy {
  driver_id: number;
  driver_name: string;
  abbreviation: string;
  team_name: string;
  stints: TyreStint[];
}

export interface DriverLapSummary {
  driver_id: number;
  driver_name: string;
  abbreviation: string;
  team_name: string;
  avg_lap_time_ms: number | null;
  best_lap_time_ms: number | null;
  median_lap_time_ms: number | null;
  total_laps: number;
  total_clean_laps: number;
}

export interface DriverComparisonResponse {
  race_id: number;
  driver1: DriverLapSummary;
  driver2: DriverLapSummary;
  sector_comparison: Record<string, unknown>;
  qualifying_comparison: Record<string, unknown>;
  race_result_comparison: Record<string, unknown>;
}

export interface PositionChange {
  driver: Pick<Driver, 'id' | 'driver_id' | 'driver_number' | 'full_name' | 'abbreviation' | 'nationality' | 'team_id'>;
  team: Team;
  qualifying_position: number | null;
  starting_position: number | null;
  finishing_position: number | null;
  classified_position: string | null;
  position_change: number | null;
}

export interface PredictionDriver {
  id: number;
  full_name: string;
  abbreviation: string;
  driver_number: number;
}

export interface PredictionTeam {
  id: number;
  name: string;
  short_name: string;
}

export interface Prediction {
  id: number;
  driver_id: number;
  driver: PredictionDriver;
  team: PredictionTeam;
  grid_position: number | null;
  predicted_position: number | null;
  predicted_rank: number;
  top10_probability: number | null;
  podium_probability: number | null;
  winner_probability: number | null;
  predicted_position_gain: number | null;
  confidence_score: number | null;
  model_version: string;
  model_context?: PredictionContext;
  feature_context?: PredictionContext;
  generated_at?: string;
}

export type PredictionContext = 'pre_qualifying' | 'post_qualifying';

export type NextRacePredictionMode = PredictionContext | 'auto';

export interface NextRacePredictionContext {
  race: Race;
  recommended_context: PredictionContext;
  qualifying_available: boolean;
  race_date: string;
  days_until_race: number;
}

export type PredictionComparisonContext = PredictionContext | 'latest';

export interface PredictionComparisonSummary {
  mae: number;
  rmse: number;
  top10_accuracy: number;
  podium_accuracy: number;
  winner_correct: boolean;
  average_position_error: number;
}

export interface PredictionDriverComparison {
  driver: PredictionDriver;
  team: PredictionTeam;
  predicted_position: number | null;
  predicted_rank: number;
  actual_position: number | null;
  actual_rank: number | null;
  position_error: number | null;
  predicted_top10: boolean;
  actual_top10: boolean;
  predicted_podium: boolean;
  actual_podium: boolean;
  points: number;
  status: string;
}

export interface PredictionComparison {
  race: Race;
  context: PredictionContext;
  model_version: string;
  summary: PredictionComparisonSummary;
  drivers: PredictionDriverComparison[];
}

export type ModelFeatureImportances = Record<string, Record<string, number>>;
export type FeatureImportances = ModelFeatureImportances | Partial<Record<PredictionContext, ModelFeatureImportances>>;

export interface ModelInfo {
  trained_at?: string;
  train_seasons?: number[];
  test_season?: number;
  models?: Record<string, Record<string, string | number | null>>;
  feature_columns?: string[];
  feature_importances?: ModelFeatureImportances;
  pre_qualifying?: ModelInfo;
  post_qualifying?: ModelInfo;
}

export type ModelLabContext = PredictionContext;
export type ModelLabTask = 'position_model' | 'top10_model' | 'podium_model' | 'position_gain_model';

export interface ModelLabExperimentSummary {
  experiment_id: string;
  completed_at: string | null;
  contexts: ModelLabContext[];
  evaluation_season: number | null;
  status: 'completed' | 'malformed';
  message: string | null;
}

export interface ModelLabExperimentList {
  experiments: ModelLabExperimentSummary[];
  latest_successful_experiment_id: string | null;
}

export interface ModelLabChampion {
  context: ModelLabContext;
  task: ModelLabTask;
  algorithm: string;
  primary_metric: string;
  primary_score: number | null;
  rank: number | null;
  metrics: Record<string, number | null>;
}

export interface ModelLabLeaderboardEntry extends ModelLabChampion {
  champion: boolean;
}

export interface ModelLabOverview {
  experiment_id: string;
  resolved_latest: boolean;
  methodology: Record<string, unknown>;
  data_summary: Record<string, unknown>;
  champions: ModelLabChampion[];
  leaderboard: ModelLabLeaderboardEntry[];
}

export interface ModelLabResultRow {
  phase: string;
  fold: string;
  context: ModelLabContext;
  task: ModelLabTask;
  algorithm: string;
  analysis_type: 'candidate_model' | 'feature_ablation';
  ablation: string | null;
  evaluation_season: number | null;
  threshold: number | null;
  threshold_selection_season: number | null;
  metrics: Record<string, number | null>;
}

export interface ModelLabResults {
  experiment_id: string;
  resolved_latest: boolean;
  analysis_type: 'candidate_model' | 'feature_ablation';
  rows: ModelLabResultRow[];
}

export interface ModelLabAblationEntry {
  context: ModelLabContext;
  task: ModelLabTask;
  ablation: string;
  algorithm: string;
  primary_metric: string;
  primary_score: number | null;
  rank: number | null;
  ablation_champion: boolean;
  best_ablation: boolean;
  metrics: Record<string, number | null>;
}

export interface ModelLabAblations {
  experiment_id: string;
  resolved_latest: boolean;
  feature_sets: Record<string, Record<string, string[]>>;
  leaderboard: ModelLabAblationEntry[];
}

export interface ModelLabArtifact {
  name: string;
  relative_path: string;
  category: 'manifest' | 'table' | 'report' | 'figure' | 'model' | 'other';
  media_type: string;
  size_bytes: number;
}

export interface ModelLabArtifacts {
  experiment_id: string;
  resolved_latest: boolean;
  artifacts: ModelLabArtifact[];
}

export interface SeasonStats {
  season: Season;
  race_count: number;
  teams: Team[];
  drivers: Driver[];
}

export interface WeatherSummary {
  race_id: number;
  avg_air_temp: number | null;
  avg_track_temp: number | null;
  max_track_temp: number | null;
  min_track_temp: number | null;
  avg_humidity: number | null;
  had_rainfall: boolean;
  samples: number;
}

export interface FastestLap {
  driver: {
    id: number;
    full_name: string;
    abbreviation: string;
  };
  team: {
    id: number;
    name: string;
  } | null;
  lap_number: number;
  lap_time_ms: number | null;
  compound: TyreCompound | string | null;
  sector1_ms: number | null;
  sector2_ms: number | null;
  sector3_ms: number | null;
}
