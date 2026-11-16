import { buildDefaultPortraitSvg, escapeXml, resolvePortraitUrl } from './portrait';

describe('portrait utils', () => {
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
