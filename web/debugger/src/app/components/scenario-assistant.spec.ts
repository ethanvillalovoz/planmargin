import { classifyAssistantQuestion } from './scenario-assistant';

describe('classifyAssistantQuestion', () => {
  it.each([
    ['How did Bayesian compare with random search?', 'method_comparison'],
    ['What happened to H1, H2, and H3?', 'hypothesis_decisions'],
    ['What did the Beam feature pipeline process?', 'beam_pipeline'],
    ['What is the defensible safety claim?', 'claim_boundary'],
    ['Summarize the development campaign results', 'campaign_overview'],
    ['What failed in the FP16 TensorRT qualification?', 'inference_qualification'],
    ['How did the trajectory model compare on ADE?', 'model_performance'],
    ['Which proposals have exact replay provenance?', 'workbench_provenance'],
  ] as const)('routes %s to %s', (question, queryId) => {
    expect(classifyAssistantQuestion(question)).toBe(queryId);
  });

  it('fails closed for questions outside the verified evidence catalog', () => {
    expect(
      classifyAssistantQuestion('How can I inspect another path planning case?'),
    ).toBeUndefined();
    expect(classifyAssistantQuestion('Tell me a joke')).toBeUndefined();
  });
});
