import { TestBed } from '@angular/core/testing';
import { App, consumeLaunchToken } from './app';
import { DebuggerStore } from './debugger.store';
import { LocalEvidenceService } from './local-evidence.service';

describe('launch session bootstrap', () => {
  afterEach(() => window.history.replaceState(null, '', '/'));

  it('consumes a fragment token and immediately removes it from the address bar', () => {
    window.history.replaceState(null, '', '/workspace?mode=local#token=abc%2F123%2Bsecure');

    expect(consumeLaunchToken(window.location, window.history)).toBe('abc/123+secure');
    expect(window.location.pathname).toBe('/workspace');
    expect(window.location.search).toBe('?mode=local');
    expect(window.location.hash).toBe('');
  });

  it('ignores unrelated or empty fragments', () => {
    window.history.replaceState(null, '', '/#view=planning');
    expect(consumeLaunchToken(window.location, window.history)).toBeUndefined();
    expect(window.location.hash).toBe('#view=planning');
  });

  it('loads the initial planning run after an automatic launch connection', async () => {
    const initialRun = { runId: 'run_opaque' };
    const connect = vi.fn().mockResolvedValue({ initialRun });
    const loadRun = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        { provide: LocalEvidenceService, useValue: { connect } },
        { provide: DebuggerStore, useValue: { loadRun } },
      ],
    });
    window.history.replaceState(null, '', '/#token=0123456789abcdef');

    TestBed.runInInjectionContext(() => new App());

    await vi.waitFor(() => expect(loadRun).toHaveBeenCalledWith(initialRun));
    expect(connect).toHaveBeenCalledWith('0123456789abcdef');
    expect(window.location.hash).toBe('');
    TestBed.resetTestingModule();
  });

  it('restores the same-tab session after a page refresh', async () => {
    const initialRun = { runId: 'run_restored' };
    const connect = vi.fn().mockResolvedValue({ initialRun });
    const restoreSessionToken = vi.fn().mockReturnValue('fedcba9876543210');
    const loadRun = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        { provide: LocalEvidenceService, useValue: { connect, restoreSessionToken } },
        { provide: DebuggerStore, useValue: { loadRun } },
      ],
    });
    window.history.replaceState(null, '', '/');

    TestBed.runInInjectionContext(() => new App());

    await vi.waitFor(() => expect(loadRun).toHaveBeenCalledWith(initialRun));
    expect(restoreSessionToken).toHaveBeenCalledOnce();
    expect(connect).toHaveBeenCalledWith('fedcba9876543210');
    TestBed.resetTestingModule();
  });
});
