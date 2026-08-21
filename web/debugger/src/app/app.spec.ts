import { TestBed } from '@angular/core/testing';
import { App, consumeLaunchToken } from './app';
import { DebuggerStore } from './debugger.store';
import { LocalEvidenceService } from './local-evidence.service';

describe('launch session bootstrap', () => {
  afterEach(() => {
    vi.useRealTimers();
    window.history.replaceState(null, '', '/');
  });

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

  it('restores the browser session after a page refresh or fresh tab', async () => {
    const initialRun = { runId: 'run_restored' };
    const restoreBrowserSession = vi.fn().mockResolvedValue({ initialRun });
    const loadRun = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        { provide: LocalEvidenceService, useValue: { restoreBrowserSession } },
        { provide: DebuggerStore, useValue: { loadRun } },
      ],
    });
    window.history.replaceState(null, '', '/');

    TestBed.runInInjectionContext(() => new App());

    await vi.waitFor(() => expect(loadRun).toHaveBeenCalledWith(initialRun));
    expect(restoreBrowserSession).toHaveBeenCalledOnce();
    TestBed.resetTestingModule();
  });

  it('retries one transient API startup failure during automatic recovery', async () => {
    vi.useFakeTimers();
    const initialRun = { runId: 'run_after_retry' };
    const restoreBrowserSession = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('temporarily unavailable'))
      .mockResolvedValueOnce({ initialRun });
    const loadRun = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        { provide: LocalEvidenceService, useValue: { restoreBrowserSession } },
        { provide: DebuggerStore, useValue: { loadRun } },
      ],
    });
    window.history.replaceState(null, '', '/');

    TestBed.runInInjectionContext(() => new App());
    await vi.advanceTimersByTimeAsync(250);

    expect(restoreBrowserSession).toHaveBeenCalledTimes(2);
    expect(loadRun).toHaveBeenCalledWith(initialRun);
    TestBed.resetTestingModule();
  });
});
