import { Droplets, Thermometer, Wind } from 'lucide-react';
import type { WeatherSummary } from '../../types';

interface WeatherPanelProps {
  weather?: WeatherSummary;
}

function value(value?: number | null) {
  return value === null || value === undefined ? '--' : value.toFixed(1);
}

export function WeatherPanel({ weather }: WeatherPanelProps) {
  return (
    <section className="card h-full p-4">
      <p className="section-label mb-4">Race Weather</p>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-sm text-f1-muted"><Thermometer className="h-4 w-4" /> Air Temp</span>
          <span className="data-value">{value(weather?.avg_air_temp)}C</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-sm text-f1-muted"><Wind className="h-4 w-4" /> Track Temp</span>
          <span className="data-value">{value(weather?.avg_track_temp)}C <span className="text-xs text-f1-muted">(max {value(weather?.max_track_temp)}C)</span></span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-sm text-f1-muted"><Droplets className="h-4 w-4" /> Humidity</span>
          <span className="data-value">{value(weather?.avg_humidity)}%</span>
        </div>
        <div className={weather?.had_rainfall ? 'rounded border border-compound-wet/40 bg-compound-wet/10 p-3 text-sm text-compound-wet' : 'rounded border border-compound-inter/40 bg-compound-inter/10 p-3 text-sm text-compound-inter'}>
          Rainfall: {weather?.had_rainfall ? 'Yes - Wet Race' : 'No - Dry Race'}
        </div>
      </div>
    </section>
  );
}
