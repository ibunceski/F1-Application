import { createContext } from 'react';

export interface SeasonContextValue {
  currentSeason: number;
  setCurrentSeason: (season: number) => void;
}

export const SeasonContext = createContext<SeasonContextValue | null>(null);
