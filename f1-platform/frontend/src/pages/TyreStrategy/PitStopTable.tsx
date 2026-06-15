import type { DriverTyreStrategy, RaceResult } from '../../types';
import { orderedStrategies } from './tyreUtils';

interface PitStopTableProps {
  strategies: DriverTyreStrategy[];
  results: RaceResult[];
}

export function PitStopTable({ strategies, results }: PitStopTableProps) {
  const rows = orderedStrategies(strategies, results).flatMap((strategy) =>
    strategy.stints.slice(1).map((stint, index) => {
      const previous = strategy.stints[index];
      return {
        driver: strategy.abbreviation,
        stop: index + 1,
        pitLap: previous.end_lap,
        compoundIn: previous.compound || 'UNKNOWN',
        compoundOut: stint.compound || 'UNKNOWN',
        before: previous.laps_on_tyre,
        after: stint.laps_on_tyre,
      };
    }),
  );

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-f1-border px-4 py-3">
        <p className="section-label">Pit Stops</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-f1-elevated text-xs uppercase text-f1-muted">
            <tr>
              <th className="px-4 py-3">Driver</th>
              <th className="px-4 py-3">Stop</th>
              <th className="px-4 py-3">Pit Lap</th>
              <th className="px-4 py-3">Compound In</th>
              <th className="px-4 py-3">Compound Out</th>
              <th className="px-4 py-3">Before</th>
              <th className="px-4 py-3">After</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-f1-border">
            {rows.map((row) => (
              <tr key={`${row.driver}-${row.stop}`}>
                <td className="px-4 py-3 font-semibold text-f1-white">{row.driver}</td>
                <td className="data-value px-4 py-3">{row.stop}</td>
                <td className="data-value px-4 py-3">{row.pitLap}</td>
                <td className="px-4 py-3 text-f1-muted">{row.compoundIn}</td>
                <td className="px-4 py-3 text-f1-muted">{row.compoundOut}</td>
                <td className="data-value px-4 py-3">{row.before} laps</td>
                <td className="data-value px-4 py-3">{row.after} laps</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-f1-border bg-f1-elevated">
              <td className="px-4 py-3 text-sm font-semibold text-f1-white" colSpan={7}>Total pit stops in race: {rows.length}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
