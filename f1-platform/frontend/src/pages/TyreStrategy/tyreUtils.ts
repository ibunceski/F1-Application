import type { DriverTyreStrategy, RaceResult, TyreStint } from '../../types';

export const compoundColors: Record<string, string> = {
  SOFT: '#FF1421',
  MEDIUM: '#FFF000',
  HARD: '#EBEBEB',
  INTERMEDIATE: '#48C774',
  INTER: '#48C774',
  WET: '#1E90FF',
  UNKNOWN: '#6B6B80',
};

export function compoundColor(compound?: string | null) {
  return compoundColors[(compound || 'UNKNOWN').toUpperCase()] || compoundColors.UNKNOWN;
}

export function orderedStrategies(strategies: DriverTyreStrategy[], results: RaceResult[]) {
  const positionByDriver = new Map(results.map((result) => [result.driver_id, result.finishing_position ?? 99]));
  return [...strategies].sort((a, b) => (positionByDriver.get(a.driver_id) ?? 99) - (positionByDriver.get(b.driver_id) ?? 99));
}

export function resultFor(strategy: DriverTyreStrategy, results: RaceResult[]) {
  return results.find((result) => result.driver_id === strategy.driver_id);
}

export function strategyPattern(stints: TyreStint[]) {
  return stints.map((stint) => stint.compound || 'UNKNOWN').join(' -> ');
}

export function pitStopCount(stints: TyreStint[]) {
  return Math.max(stints.length - 1, 0);
}
