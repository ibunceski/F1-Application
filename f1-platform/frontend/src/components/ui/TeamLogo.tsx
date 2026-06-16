import { useEffect, useMemo, useState } from 'react';
import williamsLogoUrl from '../../assets/team-logos/williams-f1.png';

interface TeamLogoProps {
  teamName: string | null | undefined;
  shortName?: string | null;
  size?: 'sm' | 'md';
}

interface TeamLogoSource {
  match: string[];
  domain: string;
  file?: string;
  files?: string[];
  urls?: string[];
  localUrl?: string;
  monochrome?: boolean;
  tone?: 'dark' | 'light';
  wide?: boolean;
  mark?: 'ferrari';
}

const teamLogoSources: TeamLogoSource[] = [
  {
    match: ['red bull'],
    domain: 'redbullracing.com',
    urls: ['https://upload.wikimedia.org/wikipedia/en/f/fa/Red_Bull_Racing_Logo_2026.svg'],
    tone: 'light',
    wide: true,
  },
  { match: ['ferrari'], domain: 'ferrari.com', mark: 'ferrari' },
  { match: ['mercedes'], file: 'Mercedes-AMG Petronas F1 Team logo (2026).svg', domain: 'mercedesamgf1.com', monochrome: true },
  { match: ['mclaren'], file: 'Logo McLaren Mastercard F1® Team 2026.svg', domain: 'mclaren.com' },
  {
    match: ['aston'],
    domain: 'astonmartinf1.com',
    urls: ['https://upload.wikimedia.org/wikipedia/fr/thumb/b/bc/Logo_Aston_Martin_Aramco_F1_Team_%282025%29.svg/960px-Logo_Aston_Martin_Aramco_F1_Team_%282025%29.svg.png'],
    tone: 'light',
    wide: true,
  },
  { match: ['alpine'], file: 'BWT Alpine F1 Team Logo.png', domain: 'alpinecars.com' },
  { match: ['williams'], domain: 'williamsf1.com', localUrl: williamsLogoUrl, tone: 'light', wide: true },
  { match: ['haas'], file: 'TGR Haas F1 Team Logo (2026).svg', domain: 'haasf1team.com' },
  {
    match: ['racing bulls', 'visa cash app rb', 'alphatauri', ' rb '],
    domain: 'visacashapprb.com',
    urls: ['https://upload.wikimedia.org/wikipedia/fr/thumb/6/6a/V-CARB.svg/960px-V-CARB.svg.png'],
    tone: 'light',
    wide: true,
  },
  { match: ['audi'], file: 'Audif1.com logo17 (cropped).svg', domain: 'audif1.com', monochrome: true },
  { match: ['cadillac'], file: 'Cadillac Formula 1 Team Logo (2025).svg', domain: 'cadillacf1team.com', monochrome: true },
  { match: ['sauber', 'kick', 'alfa romeo'], domain: 'sauber-group.com' },
];

function normalize(value: string | null | undefined) {
  return ` ${(value || '').toLowerCase()} `;
}

function wikimediaFileUrl(file: string) {
  return `https://commons.wikimedia.org/wiki/Special:Redirect/file/${encodeURIComponent(file)}`;
}

function logoConfig(teamName: string | null | undefined) {
  const normalized = normalize(teamName);
  const source = teamLogoSources.find((item) => item.match.some((match) => normalized.includes(match)));
  if (!source) return { urls: [], monochrome: false, tone: 'dark' as const, wide: false, mark: undefined };

  const urls: string[] = [];
  if (source.localUrl) urls.push(source.localUrl);
  source.urls?.forEach((url) => urls.push(url));
  source.files?.forEach((file) => urls.push(wikimediaFileUrl(file)));
  if (source.file) urls.push(wikimediaFileUrl(source.file));
  urls.push(`https://www.google.com/s2/favicons?domain=${source.domain}&sz=128`);

  return {
    urls,
    monochrome: Boolean(source.monochrome),
    tone: source.tone || 'dark',
    wide: Boolean(source.wide),
    mark: source.mark,
  };
}

function fallbackText(teamName: string | null | undefined, shortName: string | null | undefined) {
  if (shortName) return shortName.slice(0, 3).toUpperCase();
  return (teamName || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
}

function FerrariMark({ teamName, dimensions }: { teamName: string | null | undefined; dimensions: string }) {
  return (
    <span
      className={`${dimensions} inline-flex shrink-0 items-center justify-center overflow-hidden rounded border border-[#f3c000] bg-[#ffd400] p-[2px]`}
      aria-label={`${teamName || 'Ferrari'} logo`}
    >
      <img
        src="https://upload.wikimedia.org/wikipedia/en/thumb/3/36/Prancing_horse.svg/250px-Prancing_horse.svg.png"
        alt=""
        className="h-full max-w-[78%] object-contain"
        loading="lazy"
        referrerPolicy="no-referrer"
      />
    </span>
  );
}

export function TeamLogo({ teamName, shortName, size = 'sm' }: TeamLogoProps) {
  const [sourceIndex, setSourceIndex] = useState(0);
  const { urls, monochrome, tone, wide, mark } = useMemo(() => logoConfig(teamName), [teamName]);
  const src = urls[sourceIndex];
  const squareDimensions = size === 'md' ? 'h-8 w-8' : 'h-6 w-6';
  const imageDimensions = wide ? (size === 'md' ? 'h-8 w-20' : 'h-6 w-16') : squareDimensions;
  const textSize = size === 'md' ? 'text-[0.65rem]' : 'text-[0.55rem]';
  const chipTone = tone === 'light' ? 'bg-white' : 'bg-black';

  useEffect(() => {
    setSourceIndex(0);
  }, [teamName]);

  if (mark === 'ferrari') {
    return <FerrariMark teamName={teamName} dimensions={squareDimensions} />;
  }

  if (!src) {
    return (
      <span
        className={`${squareDimensions} ${textSize} inline-flex shrink-0 items-center justify-center rounded border border-f1-border bg-f1-elevated font-mono font-bold text-f1-muted`}
        aria-label={`${teamName || 'Unknown team'} logo fallback`}
      >
        {fallbackText(teamName, shortName)}
      </span>
    );
  }

  return (
    <span className={`${imageDimensions} inline-flex shrink-0 items-center justify-center rounded border border-f1-border ${chipTone} p-1`}>
      <img
        src={src}
        alt={`${teamName || 'Team'} logo`}
        className={`max-h-full max-w-full object-contain ${monochrome ? 'brightness-0 invert' : ''}`}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setSourceIndex((index) => index + 1)}
      />
    </span>
  );
}
