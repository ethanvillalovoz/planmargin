import { TestBed } from '@angular/core/testing';
import { CAMPAIGN_EVIDENCE } from '../campaign-evidence';
import { CampaignSummary } from './campaign-summary';

describe('CampaignSummary', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('renders the claim boundary and closes with Escape', async () => {
    const fixture = TestBed.createComponent(CampaignSummary);
    let closeCount = 0;
    fixture.componentInstance.close.subscribe(() => closeCount++);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('The held-out split remains unopened');
    expect(fixture.nativeElement.textContent).toContain('+14.8125 pp');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

    expect(closeCount).toBe(1);
  });

  it('closes from the backdrop without treating sheet clicks as dismissals', () => {
    const fixture = TestBed.createComponent(CampaignSummary);
    let closeCount = 0;
    fixture.componentInstance.close.subscribe(() => closeCount++);
    fixture.detectChanges();
    const backdrop = fixture.nativeElement.querySelector('.backdrop') as HTMLElement;
    const sheet = fixture.nativeElement.querySelector('.sheet') as HTMLElement;

    sheet.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(closeCount).toBe(0);
    backdrop.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(closeCount).toBe(1);
  });

  it('labels campaign evidence loaded from the authenticated local service', () => {
    const fixture = TestBed.createComponent(CampaignSummary);
    fixture.componentRef.setInput('evidence', {
      ...CAMPAIGN_EVIDENCE,
      mode: 'real-local-redacted',
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('VERIFIED LOCAL CAMPAIGN');
    expect(fixture.nativeElement.textContent).toContain('The held-out split remains unopened');
  });
});
