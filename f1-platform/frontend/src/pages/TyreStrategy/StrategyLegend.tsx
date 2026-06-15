import type { DriverTyreStrategy } from '../../types';
import { compoundColor } from './tyreUtils';

interface StrategyLegendProps {
  strategies: DriverTyreStrategy[];
}

export function StrategyLegend({ strategies }: StrategyLegendProps) {
  const compounds = Array.from(
    new Set(strategies.flatMap((strategy) => strategy.stints.map((stint) => stint.compound || 'UNKNOWN'))),
  );

  return (
    <section className="card flex flex-wrap items-center gap-3 p-4">
      <span className="section-label mr-2">Compounds</span>
      {compounds.map((compound) => (
        <span key={compound} className="inline-flex items-center gap-2 rounded-full border border-f1-border px-3 py-1 text-xs font-semibold text-f1-text">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: compoundColor(compound) }} />
          {compound}
        </span>
      ))}
    </section>
  );
}
