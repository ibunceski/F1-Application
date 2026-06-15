import type { TyreCompound } from '../../types';
import { COMPOUND_ABBREVIATIONS } from '../../lib/tyreColors';

const compoundClass: Record<TyreCompound, string> = {
  SOFT: 'bg-compound-soft text-white',
  MEDIUM: 'bg-compound-medium text-black',
  HARD: 'bg-compound-hard text-black',
  INTERMEDIATE: 'bg-compound-inter text-black',
  WET: 'bg-compound-wet text-white',
};

export function TyreBadge({ compound }: { compound: TyreCompound | string | null }) {
  if (!compound) {
    return <span className="text-xs text-f1-muted">--</span>;
  }
  const normalized = compound.toUpperCase() as TyreCompound;
  const label = COMPOUND_ABBREVIATIONS[normalized] || normalized[0];
  return (
    <span
      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
        compoundClass[normalized] || 'bg-f1-border text-f1-text'
      }`}
      title={compound}
    >
      {label}
    </span>
  );
}
