import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatLapTime } from '../../lib/formatters';
import type { LapTimesByDriver, RaceResult } from '../../types';

interface LapTimeChartProps {
  lapTimes: LapTimesByDriver[];
  results: RaceResult[];
}

const colors = ['#00D2BE', '#FF8700', '#3671C6', '#48C774', '#FFF000', '#1E90FF', '#C0C0C0', '#CD7F32', '#B6BABD', '#52E252'];

function median(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function defaultDrivers(results: RaceResult[], lapTimes: LapTimesByDriver[]) {
  const top = results
    .filter((result) => result.finishing_position !== null)
    .sort((a, b) => Number(a.finishing_position) - Number(b.finishing_position))
    .slice(0, 5)
    .map((result) => result.driver_id);
  return top.length ? top : lapTimes.slice(0, 5).map((driver) => driver.driver_id);
}

export function LapTimeChart({ lapTimes, results }: LapTimeChartProps) {
  const [visibleDrivers, setVisibleDrivers] = useState<Set<number>>(() => new Set(defaultDrivers(results, lapTimes)));
  const driversById = useMemo(() => new Map(lapTimes.map((driver) => [driver.driver_id, driver])), [lapTimes]);
  const maxLap = Math.max(0, ...lapTimes.flatMap((driver) => driver.laps.map((lap) => lap.lap_number)));

  const chartData = useMemo(() => {
    const rows = Array.from({ length: maxLap }, (_, index) => ({ lap: index + 1 } as Record<string, number | null>));
    lapTimes.forEach((driver) => {
      const times = driver.laps.map((lap) => lap.lap_time_ms).filter((value): value is number => value !== null);
      const cutoff = times.length ? median(times) * 1.3 : Infinity;
      driver.laps.forEach((lap) => {
        if (lap.lap_time_ms !== null && lap.lap_time_ms <= cutoff) {
          rows[lap.lap_number - 1][driver.abbreviation] = lap.lap_time_ms / 1000;
        }
      });
    });
    return rows;
  }, [lapTimes, maxLap]);

  function toggleDriver(driverId: number) {
    setVisibleDrivers((current) => {
      const next = new Set(current);
      if (next.has(driverId)) next.delete(driverId);
      else next.add(driverId);
      return next;
    });
  }

  function showTopFive() {
    setVisibleDrivers(new Set(defaultDrivers(results, lapTimes)));
  }

  function showAll() {
    setVisibleDrivers(new Set(lapTimes.map((driver) => driver.driver_id)));
  }

  return (
    <section className="card p-4">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <p className="section-label">Lap Time Evolution</p>
        <div className="flex gap-2">
          <button type="button" onClick={showAll} className="rounded border border-f1-border px-3 py-1.5 text-xs text-f1-text hover:border-f1-red">Show all</button>
          <button type="button" onClick={showTopFive} className="rounded border border-f1-border px-3 py-1.5 text-xs text-f1-text hover:border-f1-red">Top 5 only</button>
        </div>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {lapTimes.map((driver) => (
          <label key={driver.driver_id} className="flex items-center gap-2 rounded border border-f1-border px-2 py-1 text-xs text-f1-muted">
            <input
              type="checkbox"
              checked={visibleDrivers.has(driver.driver_id)}
              onChange={() => toggleDriver(driver.driver_id)}
              className="accent-f1-red"
            />
            {driver.abbreviation}
          </label>
        ))}
      </div>
      <div className="h-[460px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 12, right: 24, bottom: 12, left: 12 }}>
            <CartesianGrid stroke="#2A2A3D" />
            <XAxis dataKey="lap" stroke="#6B6B80" tick={{ fill: '#6B6B80' }} />
            <YAxis stroke="#6B6B80" tick={{ fill: '#6B6B80' }} tickFormatter={(value) => formatLapTime(Number(value) * 1000)} />
            <Tooltip
              contentStyle={{ background: '#111118', border: '1px solid #2A2A3D', borderRadius: 8 }}
              formatter={(value, name) => [formatLapTime(Number(value) * 1000), driversById.get([...driversById.values()].find((driver) => driver.abbreviation === name)?.driver_id || 0)?.driver_name || name]}
              labelFormatter={(label) => `Lap ${label}`}
            />
            <Legend onClick={(entry) => {
              const driver = lapTimes.find((item) => item.abbreviation === entry.value);
              if (driver) toggleDriver(driver.driver_id);
            }} />
            {lapTimes.map((driver, index) =>
              visibleDrivers.has(driver.driver_id) ? (
                <Line
                  key={driver.driver_id}
                  type="monotone"
                  dataKey={driver.abbreviation}
                  dot={false}
                  stroke={colors[index % colors.length]}
                  strokeWidth={1.5}
                  connectNulls={false}
                />
              ) : null,
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
