import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LocalEvidencePanel } from './local-evidence-panel';

describe('LocalEvidencePanel', () => {
  let fixture: ComponentFixture<LocalEvidencePanel>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [LocalEvidencePanel] }).compileComponents();
    fixture = TestBed.createComponent(LocalEvidencePanel);
    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  afterEach(() => {
    fixture.destroy();
    TestBed.resetTestingModule();
  });

  it('moves initial focus into the token field and emits close on Escape', () => {
    const input = fixture.nativeElement.querySelector('#local-token') as HTMLInputElement;
    let closed = false;
    fixture.componentInstance.close.subscribe(() => (closed = true));

    expect(document.activeElement).toBe(input);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));

    expect(closed).toBe(true);
  });

  it('wraps keyboard focus within the modal', () => {
    const buttons = fixture.nativeElement.querySelectorAll(
      'button',
    ) as NodeListOf<HTMLButtonElement>;
    const focusable = fixture.nativeElement.querySelectorAll(
      'button, input',
    ) as NodeListOf<HTMLElement>;
    focusable.forEach((element) =>
      vi.spyOn(element, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList),
    );
    const closeButton = buttons[0];
    const submitButton = buttons[buttons.length - 1];

    submitButton.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement).toBe(closeButton);

    closeButton.focus();
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }),
    );
    expect(document.activeElement).toBe(submitButton);
  });
});
