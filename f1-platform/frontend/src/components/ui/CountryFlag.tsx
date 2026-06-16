import { flagImageUrlForCountry } from '../../lib/countries';

interface CountryFlagProps {
  country: string | null | undefined;
  showName?: boolean;
  className?: string;
}

export function CountryFlag({ country, showName = false, className = '' }: CountryFlagProps) {
  const flagUrl = flagImageUrlForCountry(country);
  const label = country || 'Unknown country';

  if (!flagUrl && !showName) return null;

  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 ${className}`} title={label}>
      {flagUrl ? (
        <img
          src={flagUrl}
          alt={`${label} flag`}
          className="h-[0.9em] w-[1.35em] shrink-0 rounded-[2px] object-cover shadow-[0_0_0_1px_rgba(255,255,255,0.18)]"
          loading="lazy"
        />
      ) : null}
      {showName ? <span className="truncate">{label}</span> : null}
    </span>
  );
}
