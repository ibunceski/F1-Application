import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { useSeason } from './contexts/useSeason';
import { DriverComparison } from './pages/DriverComparison/DriverComparison';
import { ModelExplanation } from './pages/ModelExplanation/ModelExplanation';
import { NotFound } from './pages/NotFound';
import { RaceAnalysis } from './pages/RaceAnalysis/RaceAnalysis';
import { RacePredictor } from './pages/RacePredictor/RacePredictor';
import { RaceSelector } from './pages/RaceSelector';
import { SeasonOverview } from './pages/SeasonOverview/SeasonOverview';
import { TyreStrategy } from './pages/TyreStrategy/TyreStrategy';

function HomeRedirect() {
  const { currentSeason } = useSeason();
  return <Navigate to={`/seasons/${currentSeason}`} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/seasons/:year" element={<SeasonOverview />} />
          <Route path="/seasons/:year/races" element={<RaceSelector />} />
          <Route path="/seasons/:year/races/:raceId/predict" element={<RacePredictor />} />
          <Route path="/seasons/:year/races/:raceId/analysis" element={<RaceAnalysis />} />
          <Route path="/seasons/:year/races/:raceId/tyres" element={<TyreStrategy />} />
          <Route path="/drivers/compare" element={<DriverComparison />} />
          <Route path="/model" element={<ModelExplanation />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}
