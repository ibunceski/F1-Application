function positionClass(position: number) {
  if (position === 1) return 'text-podium-gold border-podium-gold';
  if (position === 2) return 'text-podium-silver border-podium-silver';
  if (position === 3) return 'text-podium-bronze border-podium-bronze';
  if (position <= 10) return 'text-f1-white border-f1-border';
  return 'text-f1-muted border-f1-border';
}

export function PositionBadge({ position }: { position: number }) {
  return (
    <span className={`inline-flex h-7 min-w-7 items-center justify-center rounded border px-2 font-mono text-xs ${positionClass(position)}`}>
      P{position}
    </span>
  );
}
