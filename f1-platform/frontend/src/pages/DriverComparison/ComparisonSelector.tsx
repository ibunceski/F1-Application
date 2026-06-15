import type { Race, RaceResult } from '../../types';

interface ComparisonSelectorProps {
  season: number;
  races: Race[];
  results: RaceResult[];
  selectedRaceId: number | null;
  driver1Id: number | null;
  driver2Id: number | null;
  onSeasonChange: (year: number) => void;
  onRaceChange: (raceId: number | null) => void;
  onDriver1Change: (driverId: number | null) => void;
  onDriver2Change: (driverId: number | null) => void;
  onCompare: () => void;
  onReset: () => void;
}

const seasons = [2021, 2022, 2023, 2024];

function completedRaces(races: Race[]) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return races.filter((race) => new Date(race.race_date) < today);
}

function selectClass() {
  return 'w-full rounded-md border border-f1-border bg-f1-elevated px-3 py-2 text-sm text-f1-text outline-none focus:border-f1-red';
}

export function ComparisonSelector({
  season,
  races,
  results,
  selectedRaceId,
  driver1Id,
  driver2Id,
  onSeasonChange,
  onRaceChange,
  onDriver1Change,
  onDriver2Change,
  onCompare,
  onReset,
}: ComparisonSelectorProps) {
  const completed = completedRaces(races);
  const canCompare = Boolean(selectedRaceId && driver1Id && driver2Id);

  return (
    <section className="card-elevated p-5">
      <div className="grid gap-4 lg:grid-cols-4">
        <label className="space-y-2">
          <span className="section-label">Season</span>
          <select value={season} onChange={(event) => onSeasonChange(Number(event.target.value))} className={selectClass()}>
            {seasons.map((year) => (
              <option key={year} value={year}>{year}</option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="section-label">Race</span>
          <select
            value={selectedRaceId ?? ''}
            onChange={(event) => onRaceChange(event.target.value ? Number(event.target.value) : null)}
            className={selectClass()}
          >
            <option value="">Select race</option>
            {completed.map((race) => (
              <option key={race.id} value={race.id}>
                R{race.round_number} - {race.race_name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="section-label">Driver 1</span>
          <select
            value={driver1Id ?? ''}
            onChange={(event) => onDriver1Change(event.target.value ? Number(event.target.value) : null)}
            disabled={!selectedRaceId}
            className={selectClass()}
          >
            <option value="">Select driver</option>
            {results.map((result) => (
              <option key={result.driver.id} value={result.driver.id}>
                {result.driver.full_name} ({result.team.short_name})
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="section-label">Driver 2</span>
          <select
            value={driver2Id ?? ''}
            onChange={(event) => onDriver2Change(event.target.value ? Number(event.target.value) : null)}
            disabled={!selectedRaceId || !driver1Id}
            className={selectClass()}
          >
            <option value="">Select driver</option>
            {results
              .filter((result) => result.driver.id !== driver1Id)
              .map((result) => (
                <option key={result.driver.id} value={result.driver.id}>
                  {result.driver.full_name} ({result.team.short_name})
                </option>
              ))}
          </select>
        </label>
      </div>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          type="button"
          disabled={!canCompare}
          onClick={onCompare}
          className="w-full rounded-md bg-f1-red px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          COMPARE
        </button>
        <button type="button" onClick={onReset} className="px-3 py-2 text-sm font-semibold text-f1-muted hover:text-f1-white">
          Reset
        </button>
      </div>
    </section>
  );
}
