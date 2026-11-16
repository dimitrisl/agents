/**
 * Escapes XML special characters so arbitrary character or class labels
 * can be interpolated safely into SVG data URIs.
 */
export function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Generates an offline-safe, deterministic SVG portrait data URI in the
 * Phyrexian dark-crimson palette with proper XML escaping.
 */
export function buildDefaultPortraitSvg(name?: string | null, charClass?: string | null): string {
  const cleanName = String(name || 'Hero').trim();
  const initial = escapeXml((cleanName.charAt(0) || 'H').toUpperCase().replace(/[^A-Z0-9]/g, 'H'));
  const cleanClass = escapeXml(String(charClass || 'Adventurer').trim().toUpperCase().slice(0, 14));
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">` +
    `<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0%" stop-color="#14141d"/><stop offset="100%" stop-color="#2a1218"/>` +
    `</linearGradient></defs>` +
    `<rect width="200" height="200" fill="url(#bg)"/>` +
    `<circle cx="100" cy="100" r="84" fill="none" stroke="#d93b48" stroke-width="2" stroke-opacity="0.45"/>` +
    `<text x="100" y="114" text-anchor="middle" fill="#f3f3f7" font-family="serif" font-size="76" font-weight="bold">${initial}</text>` +
    `<text x="100" y="158" text-anchor="middle" fill="#a0a0b2" font-family="sans-serif" font-size="14" letter-spacing="2">${cleanClass}</text>` +
    `</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

/**
 * Returns the character's portrait URL when valid, or an offline-safe default SVG fallback.
 */
export function resolvePortraitUrl(char: { char_portrait?: string | null; char_name?: string | null; char_class?: string | null } | null | undefined): string {
  const existing = char?.char_portrait;
  if (
    existing &&
    !existing.includes('anvil.png') &&
    !existing.includes('image.pollinations.ai')
  ) {
    return existing;
  }
  return buildDefaultPortraitSvg(char?.char_name, char?.char_class);
}
