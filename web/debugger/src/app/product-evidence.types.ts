export type AssistantQueryId =
  | 'campaign_overview'
  | 'method_comparison'
  | 'hypothesis_decisions'
  | 'claim_boundary'
  | 'beam_pipeline';

export interface AssistantQuestion {
  readonly query_id: AssistantQueryId;
  readonly label: string;
  readonly question: string;
}

export interface AssistantStatus {
  readonly provider_id: 'offline_deterministic' | 'gemini_public_aggregate';
  readonly model: string | null;
  readonly source_mode: 'real_local_redacted' | 'public_aggregate';
  readonly gemini_configured: boolean;
  readonly explanation_only: true;
}

export interface AssistantFact {
  readonly fact_id: string;
  readonly statement: string;
  readonly value: string | number | boolean | null;
  readonly unit: string | null;
  readonly citation_id: string;
}

export interface AssistantCitation {
  readonly citation_id: string;
  readonly title: string;
  readonly repository_path: string;
  readonly sha256: string;
}

export interface AssistantAnswer {
  readonly record_type: 'planmargin.evidence_assistant_response';
  readonly schema_version: '1.0.0';
  readonly status: 'answered';
  readonly question: {
    readonly sha256: string;
    readonly query_id: AssistantQueryId;
    readonly query_label: string;
  };
  readonly provider: {
    readonly id: 'offline_deterministic' | 'gemini_public_aggregate';
    readonly model: string | null;
    readonly role: 'explanation_only';
  };
  readonly tool_result: {
    readonly query_id: AssistantQueryId;
    readonly title: string;
    readonly source_mode: 'real_local_redacted' | 'public_aggregate';
    readonly facts: readonly AssistantFact[];
    readonly citations: readonly AssistantCitation[];
  };
  readonly explanation: {
    readonly summary: string;
    readonly interpretation: string;
    readonly cited_fact_ids: readonly string[];
    readonly limitation: string;
    readonly citation_ids: readonly string[];
  };
  readonly privacy: {
    readonly raw_question_persisted: false;
    readonly raw_question_sent_to_provider: false;
    readonly private_data_sent_to_provider: false;
    readonly provider_input_scope: 'none' | 'public_aggregate_tool_result_only';
  };
  readonly limitations: readonly string[];
}

export interface GaussianFieldSummary {
  readonly schema_version: '1.0.0';
  readonly evidence_mode: 'real_local_redacted';
  readonly decision: 'go' | 'no_go';
  readonly representation: 'deterministic_lidar_gaussian_field';
  readonly primitive_count: number;
  readonly field_bytes: number;
  readonly runtime_seconds: number;
  readonly trajectory_linkage_fraction: number;
  readonly trajectory_linkage_gate: number;
  readonly geometry: {
    readonly median_nearest_mean_distance_m: number;
    readonly p90_nearest_mean_distance_m: number;
    readonly coverage_within_0_50_m: number;
  };
  readonly gates: Readonly<Record<string, boolean>>;
  readonly claim_boundary: string;
  readonly unrestricted_export: false;
}

export interface GaussianFieldBundle {
  readonly summary: GaussianFieldSummary;
  readonly bytes: ArrayBuffer;
}

export interface SensorAssetSummary {
  readonly representation: string;
  readonly source_frame_index: number;
  readonly primitive_count: number;
  readonly bytes: number;
}

export type CameraBoxCategory = 'vehicle' | 'pedestrian' | 'cyclist';

export interface CameraBoxAnnotation {
  readonly track_id: string;
  readonly category: CameraBoxCategory;
  readonly center_x: number;
  readonly center_y: number;
  readonly width: number;
  readonly height: number;
}

export interface CameraFrameAnnotations {
  readonly index: number;
  readonly timestamp_micros: number;
  readonly boxes: readonly CameraBoxAnnotation[];
}

export interface CameraAnnotationBundle {
  readonly record_type: 'planmargin.sensor_frame_annotations';
  readonly schema_version: '1.0.0';
  readonly source: 'Waymo Open Dataset v2 Perception camera_box';
  readonly image_width: number;
  readonly image_height: number;
  readonly frames: readonly CameraFrameAnnotations[];
}

export interface SensorSceneSummary {
  readonly schema_version: '1.0.0';
  readonly evidence_mode: 'real_local_sensor';
  readonly source: 'Waymo Open Dataset v2 Perception';
  readonly segment_id: string;
  readonly camera_name: 'FRONT';
  readonly frame_count: number;
  readonly frame_rate_hz: number;
  readonly annotations: {
    readonly representation: 'native_tracked_camera_boxes';
    readonly frame_count: number;
    readonly box_count: number;
    readonly bytes: number;
  };
  readonly reconstruction: SensorAssetSummary;
  readonly reconstruction_reference?: SensorAssetSummary;
  readonly lidar: SensorAssetSummary;
  readonly trajectory?: SensorTrajectoryAssetSummary;
}

export interface SensorTrajectoryAssetSummary {
  readonly representation: 'calibrated_recorded_and_jax_predicted_ego_paths';
  readonly source_frame_index: number;
  readonly bytes: number;
  readonly future_steps: number;
  readonly step_seconds: number;
  readonly model_status: 'visualization_qualified';
}

export interface SensorTrajectoryPoint {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

export interface SensorTrajectoryOverlay {
  readonly record_type: 'planmargin.calibrated_sensor_trajectory';
  readonly schema_version: '1.0.0';
  readonly source_frame_index: number;
  readonly step_seconds: number;
  readonly future_steps: number;
  readonly coordinate_system: 'apple_sharp_source_camera_opencv';
  readonly paths: {
    readonly recorded: readonly SensorTrajectoryPoint[];
    readonly jax_prediction: readonly SensorTrajectoryPoint[];
    readonly constant_velocity: readonly SensorTrajectoryPoint[];
  };
  readonly metrics: {
    readonly jax_ade_m: number;
    readonly jax_fde_m: number;
    readonly constant_velocity_ade_m: number;
    readonly constant_velocity_fde_m: number;
  };
  readonly model: {
    readonly framework: 'JAX';
    readonly status: 'visualization_qualified';
    readonly superiority_claim_supported: false;
  };
  readonly claim_boundary: string;
}

export type SensorAssetName = 'reconstruction' | 'reconstruction_reference' | 'lidar';

export interface SensorAssetBundle {
  readonly summary: SensorSceneSummary;
  readonly bytes: ArrayBuffer;
}
