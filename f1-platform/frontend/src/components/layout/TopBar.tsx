import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useParams } from 'react-router-dom';
import { getNextRace } from '../../api/races';
import { CountryFlag } from '../ui/CountryFlag';

function breadcrumb(pathname: string, year?: string) {
  if (pathname.includes('/predict')) return `${year} Season > Prediction`;
  if (pathname.includes('/analysis')) return `${year} Season > Race Analysis`;
  if (pathname.includes('/tyres')) return `${year} Season > Tyre Strategy`;
  if (pathname.includes('/drivers/compare')) return 'Driver Comparison';
  if (pathname.includes('/model')) return 'Model Explanation';
  if (pathname.includes('/races')) return `${year} Season > Race Selection`;
  return `${year || 2024} Season`;
}

function daysUntil(date: string) {
  const today = new Date();
  const target = new Date(date);
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000);
}

export function TopBar() {
  const location = useLocation();
  const params = useParams();
  const nextRace = useQuery({ queryKey: ['next-race'], queryFn: getNextRace });
  const days = nextRace.data ? daysUntil(nextRace.data.race_date) : null;

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-f1-border bg-f1-dark/95 px-6 backdrop-blur">
      <p className="text-sm font-medium text-f1-muted">{breadcrumb(location.pathname, params.year)}</p>
      <div className="flex items-center gap-3">
        {days === 0 ? (
          <Link
            to="/predictions/next-race"
            className="rounded-full border border-f1-red px-3 py-1 text-xs font-semibold uppercase text-f1-red hover:bg-f1-red hover:text-white"
          >
            Live
          </Link>
        ) : nextRace.data ? (
          <Link to="/predictions/next-race" className="inline-flex items-center gap-1.5 text-sm text-f1-muted hover:text-f1-white">
            <CountryFlag country={nextRace.data.circuit_country} />
            Next Race: <span className="text-f1-text">{nextRace.data.race_name}</span>
            {days !== null && days > 0 ? ` in ${days} days` : ''}
          </Link>
        ) : null}
      </div>
    </header>
  );
}
