import { useContext } from 'react';
import { SeasonContext } from './seasonContextValue';

export function useSeason() {
  const context = useContext(SeasonContext);
  if (!context) {
    throw new Error('useSeason must be used within SeasonProvider');
  }
  return context;
}
