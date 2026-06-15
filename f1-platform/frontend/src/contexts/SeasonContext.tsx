import { useCallback, useMemo, useState, type PropsWithChildren } from 'react';
import { SeasonContext } from './seasonContextValue';

const defaultSeason = 2024;
const storageKey = 'f1-current-season';
function readInitialSeason() {
  const stored = window.localStorage.getItem(storageKey);
  const parsed = stored ? Number(stored) : defaultSeason;
  return Number.isFinite(parsed) ? parsed : defaultSeason;
}

export function SeasonProvider({ children }: PropsWithChildren) {
  const [currentSeason, setSeasonState] = useState(readInitialSeason);
  const setCurrentSeason = useCallback((season: number) => {
    setSeasonState(season);
    window.localStorage.setItem(storageKey, String(season));
  }, []);

  const value = useMemo(
    () => ({
      currentSeason,
      setCurrentSeason,
    }),
    [currentSeason, setCurrentSeason],
  );

  return <SeasonContext.Provider value={value}>{children}</SeasonContext.Provider>;
}
