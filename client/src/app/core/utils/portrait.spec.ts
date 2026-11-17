import {
  BrokenPortraitTracker,
  buildDefaultPortraitSvg,
  escapeXml,
  isSupportedPortraitUrl,
  resolvePortraitUrl,
  sanitizePortraitUrl,
} from './portrait';

describe('portrait utils', () => {
  it('tracks broken portrait URLs without mutating caller models', () => {
    const tracker = new BrokenPortraitTracker();
    expect(tracker.has('/api/v1/portraits/hero.png')).toBe(true);
    tracker.mark('/api/v1/portraits/hero.png');
    expect(tracker.has('/api/v1/portraits/hero.png')).toBe(false);
    expect(tracker.has('/api/v1/portraits/other.png')).toBe(true);
  });
  it('validates and sanitizes deprecated portrait URLs cleanly', () => {
    expect(isSupportedPortraitUrl('https://image.pollinations.ai/prompt/foo')).toBe(false);
    expect(isSupportedPortraitUrl('/assets/anvil.png')).toBe(false);
    expect(isSupportedPortraitUrl('data:image/svg+xml;utf8,<svg></svg>')).toBe(false);
    expect(isSupportedPortraitUrl('')).toBe(false);
    expect(isSupportedPortraitUrl(null)).toBe(false);
    expect(isSupportedPortraitUrl('/api/v1/portraits/aria.png')).toBe(true);

    expect(sanitizePortraitUrl('https://image.pollinations.ai/prompt/foo')).toBeUndefined();
    expect(sanitizePortraitUrl('data:image/svg+xml;utf8,<svg></svg>')).toBeUndefined();
    expect(sanitizePortraitUrl('/api/v1/portraits/aria.png')).toBe('/api/v1/portraits/aria.png');
  });
  it('escapes XML special characters cleanly', () => {
    expect(escapeXml(`Sword & <Shield> "A" 'B'`)).toBe(
      'Sword &amp; &lt;Shield&gt; &quot;A&quot; &apos;B&apos;'
    );
  });

  it('builds valid XML-escaped SVG data URIs when class or name contains special chars', () => {
    const uri = buildDefaultPortraitSvg('&Drizzt', 'Sword & Board <"Test">');
    expect(uri.startsWith('data:image/svg+xml;utf8,')).toBe(true);
    const decoded = decodeURIComponent(uri.replace('data:image/svg+xml;utf8,', ''));
    expect(decoded).toContain('SWORD &amp; BOARD');
    expect(decoded).not.toContain('SWORD & BOARD');
    expect(decoded).not.toContain('<"');
  });

  it('falls back from image.pollinations.ai and anvil.png URLs to default SVG', () => {
    expect(
      resolvePortraitUrl({
        char_name: 'Aria',
        char_class: 'Fighter',
        char_portrait: 'https://image.pollinations.ai/prompt/foo',
      }).startsWith('data:image/svg+xml;utf8,')
    ).toBe(true);
    expect(
      resolvePortraitUrl({
        char_name: 'Aria',
        char_class: 'Fighter',
        char_portrait: '/assets/anvil.png',
      }).startsWith('data:image/svg+xml;utf8,')
    ).toBe(true);
    expect(
      resolvePortraitUrl({
        char_name: 'Aria',
        char_class: 'Fighter',
        char_portrait: '/api/v1/portraits/aria.png',
      })
    ).toBe('/api/v1/portraits/aria.png');
  });
});
