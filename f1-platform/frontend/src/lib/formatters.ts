const constructorColors: Record<string, string> = {
  'red bull': '#3671C6',
  ferrari: '#E8002D',
  mercedes: '#00D2BE',
  mclaren: '#FF8700',
  aston: '#229971',
  alpine: '#0090FF',
  williams: '#64C4FF',
  haas: '#B6BABD',
  'racing bulls': '#6692FF',
  'visa cash app rb': '#6692FF',
  sauber: '#52E252',
  kick: '#52E252',
  'alfa romeo': '#900000',
  alphatauri: '#2B4562',
  renault: '#FFF500',
};

export function formatLapTime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '--';
  const totalSeconds = ms / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${minutes}:${seconds.toFixed(3).padStart(6, '0')}`;
}

export function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('en', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(new Date(dateStr));
}

export function formatPosition(pos: number | null | undefined): string {
  if (pos === null || pos === undefined || Number.isNaN(pos)) return '--';
  const mod100 = pos % 100;
  const mod10 = pos % 10;
  const suffix = mod100 >= 11 && mod100 <= 13 ? 'th' : mod10 === 1 ? 'st' : mod10 === 2 ? 'nd' : mod10 === 3 ? 'rd' : 'th';
  return `${pos}${suffix}`;
}

export function formatGap(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '+1 lap';
  return `${ms >= 0 ? '+' : '-'}${Math.abs(ms / 1000).toFixed(3)}s`;
}

export function formatPoints(points: number | null | undefined): string {
  if (points === null || points === undefined || Number.isNaN(points)) return '0';
  return Number.isInteger(points) ? points.toFixed(0) : points.toFixed(1);
}

export function teamColor(teamName: string | null | undefined): string {
  const normalized = (teamName || '').toLowerCase();
  const match = Object.entries(constructorColors).find(([name]) => normalized.includes(name));
  return match?.[1] || '#E8002D';
}
