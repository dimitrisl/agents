import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { marked } from 'marked';

/**
 * Renders AI-written markdown (rules answers, comparisons, NPCs, session prep…)
 * as styled HTML. The output goes through Angular's [innerHTML] sanitizer, which
 * strips scripts, event handlers and javascript: URLs, so model output cannot
 * inject code. Typography lives in `.forge-prose` in styles.css.
 */
@Component({
  selector: 'forge-markdown',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `<div class="forge-prose" [innerHTML]="html"></div>`,
})
export class ForgeMarkdownComponent {
  html = '';

  @Input() set content(markdown: string | null | undefined) {
    // gfm: tables and strikethrough, which the AI uses for comparisons.
    this.html = markdown ? (marked.parse(markdown.trim(), { gfm: true, async: false }) as string) : '';
  }
}
