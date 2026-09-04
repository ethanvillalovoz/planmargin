import { describe, expect, it } from 'vitest';
import { parseTestOperations, TEST_OPERATIONS } from './test-operations';

describe('test operations report parser', () => {
  it('accepts a verified real-data degraded report for incident inspection', () => {
    const candidate = structuredClone(TEST_OPERATIONS) as unknown as Record<string, unknown>;
    const campaign = candidate['campaign'] as Record<string, unknown>;
    campaign['execution_health'] = 'degraded';

    expect(parseTestOperations(candidate).campaign.execution_health).toBe('degraded');
  });

  it('rejects reports that do not preserve the real-data boundary', () => {
    const candidate = structuredClone(TEST_OPERATIONS) as unknown as Record<string, unknown>;
    const campaign = candidate['campaign'] as Record<string, unknown>;
    campaign['real_data_only'] = false;

    expect(() => parseTestOperations(candidate)).toThrow(
      'Operations report is not verified real-data evidence',
    );
  });
});
