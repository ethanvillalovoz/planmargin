import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LocalEvidenceService } from '../local-evidence.service';
import { SensorSceneSummary } from '../product-evidence.types';
import { SensorViewport } from './sensor-viewport';

describe('SensorViewport', () => {
  let fixture: ComponentFixture<SensorViewport>;
  const connected = signal(true);
  const sensorScene = vi.fn<() => Promise<SensorSceneSummary>>();
  const sensorAnnotations = vi.fn();
  const sensorFrame = vi.fn();

  beforeEach(async () => {
    sensorScene.mockResolvedValue({
      frame_count: 199,
      frame_rate_hz: 10,
      annotations: {
        representation: 'native_tracked_camera_boxes',
        frame_count: 199,
        box_count: 8364,
        bytes: 1_247_497,
      },
      reconstruction: { primitive_count: 1_179_648, source_frame_index: 99 },
      lidar: { primitive_count: 50_241, source_frame_index: 99 },
    } as SensorSceneSummary);
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
          useValue: { connected, sensorScene, sensorAnnotations, sensorFrame },
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
    vi.unstubAllGlobals();
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
});
