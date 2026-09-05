import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LocalEvidenceService } from '../local-evidence.service';
import { SensorSceneSummary } from '../product-evidence.types';
import { SensorViewport } from './sensor-viewport';
import { SimulatorStore } from '../simulator.store';

describe('SensorViewport', () => {
  let fixture: ComponentFixture<SensorViewport>;
  const connected = signal(true);
  const sensorScene = vi.fn<() => Promise<SensorSceneSummary>>();
  const sensorAnnotations = vi.fn();
  const sensorFrame = vi.fn();
  const sensorTrajectory = vi.fn();
  const sensorAsset = vi.fn();

  beforeEach(async () => {
    // State/lifecycle unit tests do not exercise canvas rendering. The opt-in
    // live-sensor browser check loads and renders the actual licensed assets.
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    const summary = {
      frame_count: 199,
      frame_rate_hz: 10,
      annotations: {
        representation: 'native_tracked_camera_boxes',
        frame_count: 199,
        box_count: 8364,
        bytes: 1_247_497,
      },
      reconstruction: { primitive_count: 1_179_648, source_frame_index: 20 },
      reconstruction_context: { primitive_count: 1_179_648, source_frame_index: 60 },
      lidar: { primitive_count: 50_241, source_frame_index: 99 },
    } as SensorSceneSummary;
    sensorScene.mockResolvedValue(summary);
    sensorTrajectory.mockResolvedValue(undefined);
    sensorAsset.mockResolvedValue({ summary, bytes: new ArrayBuffer(0) });
    sensorAnnotations.mockResolvedValue({
      image_width: 1920,
      image_height: 1280,
      frames: [],
    });
    sensorFrame.mockResolvedValue(new Blob([new Uint8Array([255, 216, 255, 217])]));
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:test-frame'),
      revokeObjectURL: vi.fn(),
    });
    await TestBed.configureTestingModule({
      imports: [SensorViewport],
      providers: [
        {
          provide: LocalEvidenceService,
          useValue: {
            connected,
            sensorScene,
            sensorAnnotations,
            sensorFrame,
            sensorTrajectory,
            sensorAsset,
          },
        },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    fixture?.destroy();
    connected.set(true);
    sensorScene.mockReset();
    sensorAnnotations.mockReset();
    sensorFrame.mockReset();
    sensorTrajectory.mockReset();
    sensorAsset.mockReset();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('deduplicates scene initialization when mounted while already connected', async () => {
    fixture = TestBed.createComponent(SensorViewport);
    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(sensorScene).toHaveBeenCalledTimes(1);
    expect(sensorAnnotations).toHaveBeenCalledTimes(1);
  });

  it.each(['lidar', 'reconstruction'] as const)(
    'gives the %s canvas container an accessible image role before the asset loads',
    (mode) => {
      sensorScene.mockReturnValue(new Promise(() => {}));
      TestBed.inject(SimulatorStore).selectMode(mode);
      fixture = TestBed.createComponent(SensorViewport);
      fixture.detectChanges();
      const viewport = fixture.nativeElement.querySelector('.splat-viewport') as HTMLElement;
      expect(viewport.getAttribute('role')).toBe('img');
      expect(viewport.getAttribute('aria-label')).toMatch(/Interactive/);
    },
  );

  it('restores each spatial asset source when switching modes, including cached assets', async () => {
    const simulator = TestBed.inject(SimulatorStore);
    simulator.selectMode('lidar');
    fixture = TestBed.createComponent(SensorViewport);
    // Test the real component's load/cache/state path without a WebGL device.
    const renderer = fixture.componentInstance as unknown as {
      renderSplat: () => Promise<void>;
    };
    vi.spyOn(renderer, 'renderSplat').mockResolvedValue(undefined);
    fixture.detectChanges();
    await fixture.whenStable();
    await vi.waitFor(() =>
      expect([simulator.sourceFrameIndex(), simulator.frameIndex()]).toEqual([99, 99]),
    );

    simulator.selectMode('reconstruction');
    fixture.detectChanges();
    await fixture.whenStable();
    await vi.waitFor(() => expect(simulator.frameIndex()).toBe(20));
    await vi.waitFor(() => expect(fixture.nativeElement.textContent).toContain('060 · Approach'));

    const contextButton = [...fixture.nativeElement.querySelectorAll('button')].find((button) =>
      (button as HTMLButtonElement).textContent?.includes('060 · Approach'),
    ) as HTMLButtonElement;
    contextButton.click();
    fixture.detectChanges();
    await fixture.whenStable();
    await vi.waitFor(() => expect(simulator.frameIndex()).toBe(60));

    simulator.selectMode('lidar');
    fixture.detectChanges();
    await fixture.whenStable();
    await vi.waitFor(() => expect(simulator.frameIndex()).toBe(99));

    simulator.selectMode('reconstruction');
    fixture.detectChanges();
    await fixture.whenStable();
    await vi.waitFor(() => expect(simulator.frameIndex()).toBe(60));
    expect(sensorAsset).toHaveBeenCalledTimes(3);
  });
});
