import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

function read(relativePath) {
  return readFileSync(resolve(root, relativePath), 'utf8');
}

function assertIncludes(file, needle, description) {
  const content = read(file);
  if (!content.includes(needle)) {
    throw new Error(`${description} missing in ${file}: ${needle}`);
  }
}

const checks = [
  ['src/App.tsx', '/predictions/next-race', 'Next race prediction route'],
  ['src/App.tsx', '/seasons/:year/races/:raceId/prediction-comparison', 'Prediction comparison route'],
  ['src/api/predictions.ts', '/predictions/next-race/context', 'Next race context API'],
  ['src/api/predictions.ts', '/predictions/next-race/generate', 'Next race generate API'],
  ['src/api/predictions.ts', '/predictions/races/${raceId}/comparison', 'Prediction comparison API'],
  ['src/pages/SeasonOverview/SeasonOverview.tsx', 'Predict Next Race', 'Dashboard next race CTA'],
  ['src/components/layout/TopBar.tsx', '/predictions/next-race', 'Clickable top bar next race link'],
  ['src/components/layout/Sidebar.tsx', 'Next Race', 'Sidebar next race item'],
  ['src/pages/NextRacePrediction/NextRacePrediction.tsx', 'generateNextRacePredictions', 'Next race page generation flow'],
  ['src/pages/PredictionComparison/PredictionComparison.tsx', 'Actual race results are not available yet.', 'Comparison missing-results state'],
  ['src/pages/PredictionComparison/PredictionComparison.tsx', 'Generate prediction first', 'Comparison missing-predictions CTA'],
  ['src/pages/RacePredictor/RacePredictor.tsx', 'PredictionContextSelector', 'Race predictor context selector'],
];

for (const [file, needle, description] of checks) {
  assertIncludes(file, needle, description);
}

console.log('OK: frontend prediction route smoke checks passed.');
