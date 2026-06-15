import { useMemo, useState } from 'react';
import { formatLapTime } from '../../lib/formatters';
import type { DriverTyreStrategy, RaceResult, TyreStint } from '../../types';
import { compoundColor, orderedStrategies, resultFor } from './tyreUtils';

interface StrategyTimelineProps {
  strategies: DriverTyreStrategy[];
  totalLaps: number;
  results: RaceResult[];
}

interface TooltipState {
  x: number;
  y: number;
  stint: TyreStint;
}

const leftLabelWidth = 92;
const rightPadding = 24;
const topPadding = 42;
const rowHeight = 40;
const barHeight = 24;

export function StrategyTimeline({ strategies, totalLaps, results }: StrategyTimelineProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const ordered = useMemo(() => orderedStrategies(strategies, results), [results, strategies]);
  const width = 1100;
  const plotWidth = width - leftLabelWidth - rightPadding;
  const height = topPadding + ordered.length * rowHeight + 24;
  const safeTotal = Math.max(totalLaps, 1);
  const ticks = Array.from({ length: Math.floor(safeTotal / 10) + 1 }, (_, index) => index * 10).filter((tick) => tick > 0);

  function xForLap(lap: number) {
    return leftLabelWidth + ((lap - 1) / safeTotal) * plotWidth;
  }

  return (
    <section className="card relative overflow-hidden p-4">
      <div className="mb-4 flex items-center justify-between">
        <p className="section-label">Strategy Timeline</p>
        <p className="text-xs text-f1-muted">Total laps: {totalLaps}</p>
      </div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[980px]">
          {ticks.map((tick) => {
            const x = xForLap(tick);
            return (
              <g key={tick}>
                <line x1={x} x2={x} y1={24} y2={height - 8} stroke="#2A2A3D" />
                <text x={x} y={18} fill="#6B6B80" fontSize="11" textAnchor="middle" fontFamily="JetBrains Mono">
                  {tick}
                </text>
              </g>
            );
          })}
          {ordered.map((strategy, rowIndex) => {
            const y = topPadding + rowIndex * rowHeight;
            const result = resultFor(strategy, results);
            return (
              <g key={strategy.driver_id}>
                <text x={0} y={y + 18} fill="#E8E8F0" fontSize="13" fontWeight="700">
                  {strategy.abbreviation}
                </text>
                <text x={54} y={y + 18} fill="#6B6B80" fontSize="11" fontFamily="JetBrains Mono">
                  P{result?.finishing_position ?? '--'}
                </text>
                {strategy.stints.map((stint, stintIndex) => {
                  const x = xForLap(stint.start_lap);
                  const endX = xForLap(stint.end_lap + 1);
                  const rectWidth = Math.max(endX - x - 2, 4);
                  return (
                    <g key={`${strategy.driver_id}-${stint.stint_number}-${stint.compound}`}>
                      {stintIndex > 0 ? (
                        <line x1={x - 2} x2={x - 2} y1={y + 4} y2={y + 36} stroke="#FFFFFF" strokeWidth={2} />
                      ) : null}
                      <rect
                        x={x}
                        y={y + (rowHeight - barHeight) / 2}
                        width={rectWidth}
                        height={barHeight}
                        rx={4}
                        fill={compoundColor(stint.compound)}
                        stroke="transparent"
                        onMouseEnter={(event) => setTooltip({ x: event.clientX, y: event.clientY, stint })}
                        onMouseMove={(event) => setTooltip({ x: event.clientX, y: event.clientY, stint })}
                        onMouseLeave={() => setTooltip(null)}
                        className="hover:stroke-white hover:stroke-2"
                      />
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      {tooltip ? (
        <div
          className="pointer-events-none fixed z-50 rounded border border-f1-border bg-f1-surface px-3 py-2 text-xs text-f1-text shadow-xl"
          style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
        >
          <p className="font-semibold text-f1-white">{tooltip.stint.compound} tyre</p>
          <p>Laps {tooltip.stint.start_lap}-{tooltip.stint.end_lap} ({tooltip.stint.laps_on_tyre} laps)</p>
          <p>Avg: {formatLapTime(tooltip.stint.avg_lap_time_ms)}</p>
        </div>
      ) : null}
    </section>
  );
}
