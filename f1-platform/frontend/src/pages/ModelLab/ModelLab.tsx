import { useQuery } from '@tanstack/react-query';
import { BarChart3, Beaker, CircleHelp, ExternalLink, FlaskConical, GitCompareArrows, Medal, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getModelLabAblations, getModelLabArtifacts, getModelLabExperiments, getModelLabOverview, getModelLabResults } from '../../api/modelLab';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { chartTooltipStyles } from '../../lib/chartTooltip';
import type { ModelLabContext, ModelLabLeaderboardEntry, ModelLabTask } from '../../types';

const tasks: Array<{ key: ModelLabTask; label: string; description: string }> = [
  { key: 'position_model', label: 'Finishing position', description: 'Regression: predicted classified finishing position.' },
  { key: 'top10_model', label: 'Top 10', description: 'Classification: probability of a Top 10 finish.' },
  { key: 'podium_model', label: 'Podium', description: 'Classification: probability of a Top 3 finish.' },
  { key: 'position_gain_model', label: 'Gain / loss', description: 'Regression: net positions gained or lost.' },
];

const metricHelp: Record<string, string> = {
  mae: 'Mean Absolute Error: average position error. Lower is better and easy to interpret in grid positions.',
  pr_auc: 'Precision–Recall AUC: emphasises the positive class, making it the primary podium metric when podium finishes are rare.',
  roc_auc: 'ROC-AUC: measures discrimination across every probability threshold; higher means positives rank above negatives more often.',
  brier: 'Brier score: mean squared probability error. Lower values indicate better-calibrated probabilities.',
  mean_race_spearman: 'Mean per-race Spearman rank correlation: evaluates whether a finishing-position model orders drivers correctly within each race.',
};

function titleCase(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function contextLabel(context: ModelLabContext) {
  return context === 'pre_qualifying' ? 'Pre-qualifying' : 'Post-qualifying';
}

function score(value: number | null | undefined) {
  return typeof value === 'number' ? value.toFixed(3) : '—';
}

function isLowerBetter(metric: string) {
  return ['mae', 'rmse', 'brier', 'log_loss'].includes(metric);
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function metricLabel(metric: string) {
  return metricHelp[metric] ? <MetricHint metric={metric} /> : titleCase(metric);
}

function MetricHint({ metric }: { metric: string }) {
  return (
    <span className="inline-flex items-center gap-1" title={metricHelp[metric]}>
      {metric.toUpperCase().replace('_', '-')}
      <CircleHelp className="h-3.5 w-3.5 text-f1-muted" aria-label={metricHelp[metric]} />
    </span>
  );
}

function ModelLabLeaderboard({ entries, evaluationSeason }: { entries: ModelLabLeaderboardEntry[]; evaluationSeason?: number }) {
  const [ascending, setAscending] = useState<boolean | null>(null);
  const sorted = useMemo(() => {
    const copy = [...entries];
    return copy.sort((left, right) => {
      const lower = isLowerBetter(left.primary_metric);
      const direction = ascending === null ? (lower ? 1 : -1) : (ascending ? 1 : -1);
      return ((left.primary_score ?? Number.POSITIVE_INFINITY) - (right.primary_score ?? Number.POSITIVE_INFINITY)) * direction;
    });
  }, [ascending, entries]);

  if (!entries.length) return <EmptyState title="No comparable models" description="This experiment does not contain leaderboard rows for the selected task and context." icon={BarChart3} />;

  return (
    <div className="overflow-x-auto rounded-lg border border-f1-border">
      <table className="w-full min-w-[700px] text-left text-sm">
        <thead className="bg-f1-elevated text-xs uppercase tracking-wider text-f1-muted">
          <tr>
            <th className="px-4 py-3">Model</th>
            <th className="px-4 py-3">Context</th>
            <th className="px-4 py-3">
              <button type="button" onClick={() => setAscending((current) => current === null ? true : !current)} className="inline-flex items-center gap-1 hover:text-f1-white">
                Metric <GitCompareArrows className="h-3.5 w-3.5" />
              </button>
            </th>
            <th className="px-4 py-3">Validation score</th>
            <th className="px-4 py-3">Evaluation evidence</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((entry) => (
            <tr key={`${entry.context}-${entry.algorithm}`} className={entry.champion ? 'bg-f1-red/10' : 'border-t border-f1-border/70'}>
              <td className="px-4 py-3 font-semibold text-f1-white">
                <div className="flex items-center gap-2">
                  {entry.champion ? <Medal className="h-4 w-4 text-amber-300" aria-label="Validation champion" /> : null}
                  {entry.algorithm}
                </div>
              </td>
              <td className="px-4 py-3 text-f1-text">{contextLabel(entry.context)}</td>
              <td className="px-4 py-3 text-f1-text">{metricLabel(entry.primary_metric)}</td>
              <td className="px-4 py-3 font-mono text-f1-white">{score(entry.primary_score)}</td>
              <td className="px-4 py-3 text-xs text-f1-muted">Rolling validation · final holdout {evaluationSeason ?? 'recorded in artifact'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ModelLab() {
  const experiments = useQuery({ queryKey: ['model-lab', 'experiments'], queryFn: getModelLabExperiments });
  const [selectedExperiment, setSelectedExperiment] = useState<string | undefined>();
  const [activeTask, setActiveTask] = useState<ModelLabTask>('position_model');
  const [context, setContext] = useState<ModelLabContext | 'all'>('all');

  useEffect(() => {
    if (!selectedExperiment && experiments.data?.latest_successful_experiment_id) {
      setSelectedExperiment(experiments.data.latest_successful_experiment_id);
    }
  }, [experiments.data?.latest_successful_experiment_id, selectedExperiment]);

  const overview = useQuery({ queryKey: ['model-lab', 'overview', selectedExperiment], queryFn: () => getModelLabOverview(selectedExperiment), enabled: Boolean(selectedExperiment) });
  const ablations = useQuery({
    queryKey: ['model-lab', 'ablations', selectedExperiment, activeTask, context],
    queryFn: () => getModelLabAblations({ experimentId: selectedExperiment, task: activeTask, context: context === 'all' ? undefined : context }),
    enabled: Boolean(selectedExperiment),
  });
  const results = useQuery({
    queryKey: ['model-lab', 'results', selectedExperiment, activeTask, context],
    queryFn: () => getModelLabResults({ experimentId: selectedExperiment, task: activeTask, context: context === 'all' ? undefined : context }),
    enabled: Boolean(selectedExperiment),
  });
  const artifacts = useQuery({ queryKey: ['model-lab', 'artifacts', selectedExperiment], queryFn: () => getModelLabArtifacts(selectedExperiment), enabled: Boolean(selectedExperiment) });

  if (experiments.isLoading) return <LoadingSpinner />;
  if (experiments.isError) return <ErrorState message="Model Lab experiments could not be loaded." onRetry={() => void experiments.refetch()} />;
  if (!experiments.data?.latest_successful_experiment_id) {
    return <EmptyState title="No completed experiments yet" description="Model Lab becomes available after a completed experiment has written valid artifacts. Prediction pages remain available independently." icon={FlaskConical} />;
  }
  if (overview.isLoading) return <LoadingSpinner />;
  if (overview.isError || !overview.data) return <ErrorState message="The selected experiment is missing or incomplete." onRetry={() => void overview.refetch()} />;

  const selectedTask = tasks.find((task) => task.key === activeTask) ?? tasks[0];
  const visibleEntries = overview.data.leaderboard.filter((entry) => entry.task === activeTask && (context === 'all' || entry.context === context));
  const champion = visibleEntries.find((entry) => entry.champion);
  const comparisonData = overview.data.champions
    .filter((entry) => entry.task === activeTask)
    .map((entry) => ({ context: contextLabel(entry.context), score: entry.primary_score ?? 0, metric: entry.primary_metric }));
  const ablationData = (ablations.data?.leaderboard ?? [])
    .filter((entry) => context === 'all' || entry.context === context)
    .filter((entry) => entry.ablation_champion)
    .map((entry) => ({ label: `${contextLabel(entry.context)} · ${titleCase(entry.ablation)}`, score: entry.primary_score ?? 0, metric: entry.primary_metric, best: entry.best_ablation }));
  const method = record(overview.data.methodology);
  const configuration = record(method.configuration);
  const dataSummary = record(overview.data.data_summary);
  const sampleCounts = record(dataSummary.sample_counts);
  const contexts = method.contexts;
  const figureCount = artifacts.data?.artifacts.filter((artifact) => artifact.category === 'figure').length ?? 0;

  return (
    <div className="space-y-7">
      <header className="border-b border-f1-border pb-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-label">Thesis Model Comparison</p>
            <h1 className="mt-2 text-3xl font-bold text-f1-white">Model Lab</h1>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-f1-muted">Compare reproducible temporal experiments across four F1 prediction tasks. This is distinct from the race-level prediction-versus-actual outcome page.</p>
          </div>
          <Link to="/model" className="inline-flex items-center gap-2 rounded border border-f1-border px-3 py-2 text-sm font-semibold text-f1-text hover:border-f1-red hover:text-f1-white">
            Feature importance explanation <ExternalLink className="h-4 w-4" />
          </Link>
        </div>
      </header>

      <section className="card-elevated grid gap-4 p-4 lg:grid-cols-2">
        <label className="text-sm font-semibold text-f1-text">
          Experiment artifact
          <select value={selectedExperiment ?? ''} onChange={(event) => setSelectedExperiment(event.target.value)} className="mt-2 w-full rounded border border-f1-border bg-f1-dark px-3 py-2 text-sm text-f1-white outline-none focus:border-f1-red">
            {experiments.data.experiments.filter((experiment) => experiment.status === 'completed').map((experiment) => (
              <option key={experiment.experiment_id} value={experiment.experiment_id}>{experiment.experiment_id} · holdout {experiment.evaluation_season ?? '—'}</option>
            ))}
          </select>
        </label>
        <div>
          <p className="text-sm font-semibold text-f1-text">Feature context</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(['all', 'pre_qualifying', 'post_qualifying'] as const).map((value) => (
              <button key={value} type="button" onClick={() => setContext(value)} className={`rounded border px-3 py-2 text-sm font-semibold ${context === value ? 'border-f1-red bg-f1-red/10 text-f1-white' : 'border-f1-border text-f1-muted hover:text-f1-white'}`}>
                {value === 'all' ? 'All contexts' : contextLabel(value)}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <article className="card-elevated p-4"><p className="section-label">Holdout season</p><p className="data-value mt-2 text-xl">{String(method.evaluation_season ?? '—')}</p></article>
        <article className="card-elevated p-4"><p className="section-label">Random seed</p><p className="data-value mt-2 text-xl">{String(method.seed ?? '—')}</p></article>
        <article className="card-elevated p-4"><p className="section-label">Temporal validation</p><p className="mt-2 text-sm font-semibold text-f1-white">{String(configuration.validation_strategy ?? 'Recorded in artifact').replace(/_/g, ' ')}</p></article>
        <article className="card-elevated p-4"><p className="section-label">Feature contexts</p><p className="mt-2 text-sm font-semibold text-f1-white">{Array.isArray(contexts) ? contexts.map((item) => titleCase(String(item))).join(' · ') : '—'}</p></article>
        <article className="card-elevated p-4"><p className="section-label">Figure artifacts</p><p className="data-value mt-2 text-xl">{figureCount}</p></article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <article className="card-elevated p-5">
          <p className="section-label">Dataset & protocol</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <p className="text-sm text-f1-muted">Development seasons: <span className="font-semibold text-f1-text">{Array.isArray(method.train_seasons) ? method.train_seasons.join(', ') : 'recorded in manifest'}</span></p>
            <p className="text-sm text-f1-muted">Rows by context: <span className="font-semibold text-f1-text">{Object.entries(sampleCounts).map(([key, value]) => `${titleCase(key)} ${Object.values(record(value)).reduce<number>((sum, count) => sum + Number(count || 0), 0)}`).join(' · ') || '—'}</span></p>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-f1-muted">Only completed seasons enter temporal validation and the held-out test. Scores below always identify their task, context, validation period, and final holdout season before any champion label is shown.</p>
        </article>
        <article className="rounded-lg border border-amber-400/40 bg-amber-400/5 p-5">
          <p className="section-label text-amber-200">Limitations</p>
          <p className="mt-3 text-sm leading-relaxed text-f1-text">Safety cars, incidents, strategy shifts, and race-session weather are not known at the prediction cutoff. Artifact figures are metadata-only here; their underlying comparison data is visualized below.</p>
        </article>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap gap-2 border-b border-f1-border pb-3">
          {tasks.map((task) => <button key={task.key} type="button" onClick={() => setActiveTask(task.key)} className={`rounded border px-3 py-2 text-sm font-semibold ${activeTask === task.key ? 'border-f1-red bg-f1-elevated text-f1-white' : 'border-f1-border text-f1-muted hover:text-f1-white'}`}>{task.label}</button>)}
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><p className="section-label">Candidate model comparison</p><h2 className="mt-1 text-xl font-bold text-f1-white">{selectedTask.label}</h2><p className="mt-1 text-sm text-f1-muted">{selectedTask.description}</p></div>
          {champion ? <Link to="/model" className="rounded border border-amber-300/50 bg-amber-300/10 px-3 py-2 text-xs font-semibold text-amber-100 hover:border-amber-300">Champion: {champion.algorithm} · {metricLabel(champion.primary_metric)} {score(champion.primary_score)} · feature explanation</Link> : null}
        </div>
        <ModelLabLeaderboard entries={visibleEntries} evaluationSeason={Number(method.evaluation_season) || undefined} />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <article className="card-elevated p-5"><p className="section-label">Information-set comparison</p><h2 className="mt-1 text-lg font-bold text-f1-white">Pre-qualifying vs post-qualifying</h2><p className="mt-1 text-xs text-f1-muted">Validation champions for {selectedTask.label}; metric label is retained in the tooltip.</p><div className="mt-4 h-72">{comparisonData.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={comparisonData}><CartesianGrid stroke="#2A2A3D" vertical={false} /><XAxis dataKey="context" stroke="#6B6B80" tick={{ fill: '#C9C9D2', fontSize: 12 }} /><YAxis stroke="#6B6B80" tick={{ fill: '#6B6B80' }} /><Tooltip {...chartTooltipStyles} formatter={(value) => [score(Number(value)), 'Validation score']} /><Bar dataKey="score" radius={[5, 5, 0, 0]}>{comparisonData.map((row) => <Cell key={row.context} fill={row.context.startsWith('Post') ? '#E8002D' : '#4C78A8'} />)}</Bar></BarChart></ResponsiveContainer> : <EmptyState title="Contexts unavailable" description="This experiment has no champion rows for both contexts." />}</div></article>
        <article className="card-elevated p-5"><p className="section-label">Feature ablation</p><h2 className="mt-1 text-lg font-bold text-f1-white">What information moves performance?</h2><p className="mt-1 text-xs text-f1-muted">Each bar is the validation-selected model for its feature subset, not a prediction outcome score.</p><div className="mt-4 h-72">{ablations.isLoading ? <LoadingSpinner /> : ablationData.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={ablationData} layout="vertical" margin={{ left: 8, right: 16 }}><CartesianGrid stroke="#2A2A3D" horizontal={false} /><XAxis type="number" stroke="#6B6B80" tick={{ fill: '#6B6B80' }} /><YAxis type="category" dataKey="label" width={160} stroke="#6B6B80" tick={{ fill: '#C9C9D2', fontSize: 11 }} /><Tooltip {...chartTooltipStyles} formatter={(value) => [score(Number(value)), 'Validation score']} /><Bar dataKey="score" radius={[0, 5, 5, 0]}>{ablationData.map((row) => <Cell key={row.label} fill={row.best ? '#E8002D' : '#4C78A8'} />)}</Bar></BarChart></ResponsiveContainer> : <EmptyState title="No ablation artifact" description="Feature-ablation results are unavailable for this selected experiment." icon={Beaker} />}</div></article>
      </section>

      <section className="card-elevated p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="section-label">Evaluation rows</p><h2 className="mt-1 text-lg font-bold text-f1-white">Saved fold and holdout evidence</h2></div><button type="button" onClick={() => { void results.refetch(); void ablations.refetch(); void artifacts.refetch(); }} className="inline-flex items-center gap-2 rounded border border-f1-border px-3 py-2 text-sm text-f1-text hover:border-f1-red"><RefreshCw className="h-4 w-4" /> Refresh artifacts</button></div>
        {results.isError ? <p className="mt-4 text-sm text-f1-red">Result rows could not be read from this artifact.</p> : <div className="mt-4 grid gap-3 sm:grid-cols-3">{results.data?.rows.slice(0, 3).map((row) => <div key={`${row.fold}-${row.algorithm}`} className="rounded border border-f1-border bg-f1-dark/50 p-3"><p className="text-xs uppercase tracking-wider text-f1-muted">{row.phase} · {row.fold}</p><p className="mt-1 font-semibold text-f1-white">{row.algorithm}</p><p className="mt-1 text-xs text-f1-muted">Evaluation season {row.evaluation_season ?? '—'} · {row.threshold !== null ? `threshold ${row.threshold.toFixed(2)}` : 'regression'}</p></div>) ?? <p className="text-sm text-f1-muted">No result rows match the selected filters.</p>}</div>}
        <div className="mt-5 border-t border-f1-border pt-4">
          <p className="section-label">Generated thesis figures</p>
          <p className="mt-1 text-xs text-f1-muted">Artifact metadata confirms the CSV-backed figures generated by the experiment runner; the charts above render the same API evidence in-app.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {artifacts.data?.artifacts.filter((artifact) => artifact.category === 'figure').map((artifact) => <span key={artifact.relative_path} className="rounded border border-f1-border bg-f1-dark/50 px-2 py-1 font-mono text-xs text-f1-text">{artifact.name}</span>)}
            {!artifacts.data?.artifacts.some((artifact) => artifact.category === 'figure') ? <span className="text-sm text-f1-muted">No figure artifacts were generated for this experiment.</span> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
