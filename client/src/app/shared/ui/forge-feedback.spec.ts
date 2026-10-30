import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import {
  ForgeButtonDirective,
  ForgeIconComponent,
  ForgeInputDirective,
  ForgeSelectDirective,
  ForgeSkeletonComponent,
  ForgeSpinnerComponent,
} from './index';

@Component({
  standalone: true,
  imports: [ForgeButtonDirective, ForgeIconComponent, ForgeInputDirective, ForgeSelectDirective, ForgeSpinnerComponent, ForgeSkeletonComponent],
  template: `
    <button id="save" forgeButton [loading]="loading" [disabled]="disabled">Save</button>
    <a id="link" forgeButton [loading]="loading">Go</a>
    <button id="close" forgeButton variant="ghost" iconOnly aria-label="Close"><forge-icon name="close" /></button>
    <forge-spinner label="Loading spells" />
    <forge-skeleton [lines]="3" />
    <forge-skeleton shape="circle" class="h-12 w-12" />
    <button id="neutral" forgeButton variant="secondary">Edit</button>
    <button id="danger" forgeButton variant="secondary" tone="danger">Damage</button>
    <button id="success" forgeButton variant="secondary" tone="success">Heal</button>
    <input id="regular" forgeInput />
    <input id="dense" forgeInput dense />
    <select id="dense-select" forgeSelect dense></select>
  `,
})
class HostComponent {
  loading = false;
  disabled = false;
}

describe('forge-* feedback kit', () => {
  let fixture: ComponentFixture<HostComponent>;
  let el: HTMLElement;

  beforeEach(() => {
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    el = fixture.nativeElement;
  });

  const save = () => el.querySelector<HTMLButtonElement>('#save')!;

  it('[loading] disables the button, marks it busy and shows the spinner class', () => {
    expect(save().disabled).toBe(false);
    expect(save().getAttribute('aria-busy')).toBeNull();

    fixture.componentInstance.loading = true;
    fixture.detectChanges();

    expect(save().disabled).toBe(true);
    expect(save().getAttribute('aria-busy')).toBe('true');
    expect(save().classList).toContain('forge-btn-loading');
    // A loading button is not dimmed like a plain disabled one.
    expect(save().className).not.toContain('disabled:opacity-50');
    // Also valid on links, where `disabled` is only an attribute.
    expect(el.querySelector('#link')!.hasAttribute('disabled')).toBe(true);
  });

  it('keeps a plain [disabled] binding working', () => {
    fixture.componentInstance.disabled = true;
    fixture.detectChanges();
    expect(save().disabled).toBe(true);
    expect(save().getAttribute('aria-busy')).toBeNull();
    expect(save().className).toContain('disabled:opacity-50');
  });

  it('renders the close icon as decorative SVG, labelled by its button', () => {
    const icon = el.querySelector('#close forge-icon')!;
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(icon.querySelector('svg path')).not.toBeNull();
    expect(el.querySelector('#close')!.getAttribute('aria-label')).toBe('Close');
  });

  it('announces the spinner label to screen readers', () => {
    const spinner = el.querySelector('forge-spinner')!;
    expect(spinner.getAttribute('role')).toBe('status');
    expect(spinner.textContent).toContain('Loading spells');
  });

  it('draws skeleton lines with a shorter last line, and keeps host sizing on shapes', () => {
    const [text, circle] = Array.from(el.querySelectorAll('forge-skeleton'));
    const lines = text.querySelectorAll('span');
    expect(lines.length).toBe(3);
    expect(lines[2].className).toContain('w-3/5');
    expect(text.getAttribute('aria-hidden')).toBe('true');

    expect(circle.className).toContain('rounded-full');
    expect(circle.className).toContain('h-12');
    expect(circle.className).not.toContain('w-full');
  });

  it('secondary tones replace the neutral colors instead of stacking on them', () => {
    const cls = (id: string) => el.querySelector(`#${id}`)!.className;
    expect(cls('neutral')).toContain('text-muted');
    expect(cls('danger')).toContain('text-red');
    expect(cls('danger')).not.toContain('text-muted');
    expect(cls('success')).toContain('text-emerald');
    expect(cls('success')).not.toContain('border-hairline');
  });

  it('dense form controls swap their padding/size instead of needing !important overrides', () => {
    const cls = (id: string) => el.querySelector(`#${id}`)!.className;
    expect(cls('regular')).toContain('py-2.5');
    expect(cls('dense')).toContain('py-1.5');
    expect(cls('dense')).not.toContain('py-2.5');
    expect(cls('dense')).toContain('text-label');
    expect(cls('dense-select')).toContain('pr-8');
    expect(cls('dense-select')).not.toContain('pr-10');
  });
});
