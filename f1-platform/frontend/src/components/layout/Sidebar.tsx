import { BarChart2, Brain, CalendarClock, CircleDot, FlaskConical, LayoutDashboard, Target, Users } from 'lucide-react';
import { useEffect } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useSeason } from '../../contexts/useSeason';

const seasons = [2021, 2022, 2023, 2024, 2025, 2026];

function seasonFromParams(value?: string) {
  const parsed = Number(value);
  return seasons.includes(parsed) ? parsed : seasons[seasons.length - 1];
}

export function Sidebar() {
  const params = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { currentSeason, setCurrentSeason } = useSeason();
  const currentYear = params.year ? seasonFromParams(params.year) : currentSeason;

  useEffect(() => {
    if (params.year) {
      setCurrentSeason(seasonFromParams(params.year));
    }
  }, [params.year, setCurrentSeason]);

  const items = [
    { label: 'Dashboard', icon: LayoutDashboard, to: `/seasons/${currentYear}` },
    { label: 'Model Lab', icon: FlaskConical, to: '/model-lab' },
    { label: 'Next Race', icon: CalendarClock, to: '/predictions/next-race' },
    { label: 'Race Predictor', icon: Target, to: `/seasons/${currentYear}/races?view=predict` },
    { label: 'Race Analysis', icon: BarChart2, to: `/seasons/${currentYear}/races?view=analysis` },
    { label: 'Tyre Strategy', icon: CircleDot, to: `/seasons/${currentYear}/races?view=tyres` },
    { label: 'Driver Comparison', icon: Users, to: '/drivers/compare' },
    { label: 'Model Info', icon: Brain, to: '/model' },
  ];

  function isItemActive(to: string) {
    const [pathname, search = ''] = to.split('?');
    const view = new URLSearchParams(search).get('view');
    if (view === 'predict') return location.pathname === pathname && location.search === `?${search}` || location.pathname.endsWith('/predict');
    if (view === 'analysis') return location.pathname === pathname && location.search === `?${search}` || location.pathname.endsWith('/analysis');
    if (view === 'tyres') return location.pathname === pathname && location.search === `?${search}` || location.pathname.endsWith('/tyres');
    if (search) {
      return location.pathname === pathname && location.search === `?${search}`;
    }
    return location.pathname === pathname || (pathname !== `/seasons/${currentYear}` && location.pathname.startsWith(pathname));
  }

  function itemClass(active: boolean) {
    return `flex items-center gap-3 rounded-md border-l-2 px-3 py-2.5 text-sm font-medium transition ${
      active
        ? 'border-f1-red bg-f1-elevated text-f1-white'
        : 'border-transparent text-f1-muted hover:bg-f1-elevated hover:text-f1-text'
    }`;
  }

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-f1-border bg-f1-surface lg:flex">
        <div className="border-b border-f1-border px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded bg-f1-red font-display text-sm font-black text-white">
              F1
            </div>
            <div>
              <p className="text-sm font-bold text-f1-white">Race Prediction</p>
              <p className="text-xs text-f1-muted">Analytics Platform</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {items.map((item) => (
            <Link key={item.label} to={item.to} className={itemClass(isItemActive(item.to))}>
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-f1-border p-4">
          <label className="section-label mb-2 block" htmlFor="season-select">
            Season
          </label>
          <select
            id="season-select"
            value={currentYear}
            onChange={(event) => {
              const season = Number(event.target.value);
              setCurrentSeason(season);
              navigate(`/seasons/${season}`);
            }}
            className="w-full rounded-md border border-f1-border bg-f1-elevated px-3 py-2 text-sm text-f1-text outline-none focus:border-f1-red"
          >
            {seasons.map((season) => (
              <option key={season} value={season}>
                {season}
              </option>
            ))}
          </select>
        </div>
      </aside>
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-f1-border bg-f1-surface lg:hidden">
        {items.slice(0, 5).map((item) => (
          <Link
            key={item.label}
            to={item.to}
            className={`flex flex-col items-center gap-1 px-1 py-2 text-[0.65rem] font-medium ${
              isItemActive(item.to) ? 'text-f1-red' : 'text-f1-muted'
            }`}
          >
            <item.icon className="h-4 w-4" />
            <span className="max-w-full truncate">{item.label.replace('Race ', '')}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
