const countryAliases: Record<string, string> = {
  'abu dhabi': 'AE',
  australia: 'AU',
  austria: 'AT',
  azerbaijan: 'AZ',
  bahrain: 'BH',
  belgium: 'BE',
  brazil: 'BR',
  canada: 'CA',
  china: 'CN',
  france: 'FR',
  germany: 'DE',
  'great britain': 'GB',
  hungary: 'HU',
  italy: 'IT',
  japan: 'JP',
  'las vegas': 'US',
  mexico: 'MX',
  monaco: 'MC',
  netherlands: 'NL',
  qatar: 'QA',
  'saudi arabia': 'SA',
  singapore: 'SG',
  spain: 'ES',
  uae: 'AE',
  uk: 'GB',
  'united arab emirates': 'AE',
  'united kingdom': 'GB',
  'united states': 'US',
  usa: 'US',
};

function normalizeCountry(value: string) {
  return value
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export function countryCodeFromName(country: string | null | undefined) {
  if (!country) return null;
  const trimmed = country.trim();
  if (/^[a-z]{2}$/i.test(trimmed)) return trimmed.toUpperCase();
  return countryAliases[normalizeCountry(trimmed)] || null;
}

export function flagEmojiFromCountryCode(countryCode: string | null | undefined) {
  if (!countryCode || !/^[A-Z]{2}$/.test(countryCode)) return null;

  return [...countryCode]
    .map((char) => String.fromCodePoint(127397 + char.charCodeAt(0)))
    .join('');
}

export function flagEmojiForCountry(country: string | null | undefined) {
  return flagEmojiFromCountryCode(countryCodeFromName(country));
}

export function flagImageUrlForCountry(country: string | null | undefined) {
  const countryCode = countryCodeFromName(country);
  if (!countryCode) return null;
  return `https://flagcdn.com/${countryCode.toLowerCase()}.svg`;
}
