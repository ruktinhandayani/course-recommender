export type DataMode = "test" | "normal";

export interface HealthResponse {
  status: string;
  model_version: string;
  generated_at: string | null;
  export_ready: boolean;
  artifact_status: string | null;
  recommendation_count: number;
  primary_ranking?: string;
  export_mode?: string | null;
  active_export_users?: number | null;
  active_export_top_k?: number | null;
}

export interface Recommendation {
  canonical_course_id: string;
  rank: number;
  score: number;
  reason_code: string | null;
  course_title: string | null;
  competency: string | null;
  level: string | null;
  certificate_status: string | null;
  similarity_score: number | null;
  similarity_score_percent: number | null;
  softmax_score: number | null;
  softmax_score_percent: number | null;
  fallback_reason: string | null;
  recommendation_reason: string | null;
}

export interface EmployeeProfile {
  employee_name: string;
  user_id: string;
  source_system: string;
  history_count: number;
  id_match_type: string;
}

export interface CourseHistoryItem {
  event_timestamp: string | null;
  course_id: string;
  course_name: string;
  competency: string;
  level: string;
  certificate_status: string;
}

export interface AttentionItem {
  input_position: number;
  course_id: string;
  course_name: string;
  attention_weight: number;
}

export interface ActualCourseCheck {
  course_id: string;
  course_name: string;
  rank: number | null;
  status: string;
}

export interface LearningProgressSummary {
  status_available: boolean;
  tracked_course_count: number;
  completed_count: number;
  ongoing_count: number;
  enrolled_count: number;
  unenrolled_count: number;
  completion_rate_percent: number | null;
  average_score: number | null;
  score_count: number;
  certificate_count: number;
  note: string;
}

export interface LearningProgressItem {
  course_id: string;
  course_name: string;
  learning_status: string;
  score: number | null;
  has_certificate: boolean;
}

export interface UserResponse {
  request_id: string;
  user_id: string;
  requested_user_id: string;
  canonical_user_id: string;
  match_type: string;
  model_version: string;
  generated_at: string;
  recommendations: Recommendation[];
  profile: EmployeeProfile | null;
  history: CourseHistoryItem[];
  attention: AttentionItem[];
  actual_course: ActualCourseCheck | null;
  learning_progress: LearningProgressSummary | null;
  progress_items: LearningProgressItem[];
  inference_source: "active_export" | "live_model";
}

export interface ExportRecommendation extends Recommendation {
  user_id: string;
}

export interface ExportResponse {
  request_id: string;
  model_version: string;
  generated_at: string;
  page: {
    limit: number;
    next_cursor: string | null;
    has_more: boolean;
  };
  recommendations: ExportRecommendation[];
}

export interface AuthUser {
  authenticated: boolean;
  username: string | null;
}

export interface EvaluationMetric {
  label: string;
  value: number | null;
  context: string;
}

export interface EvaluationResponse {
  model_version: string;
  primary_ranking: string;
  masking_protocol: string;
  export_mode?: string | null;
  active_export_users?: number | null;
  active_export_top_k?: number | null;
  evaluation_samples: number | null;
  generated_at: string | null;
  overall_metrics: EvaluationMetric[];
  metric_tables: Record<string, Record<string, unknown>[]>;
}

export interface ResearchSummaryResponse {
  model_version: string;
  primary_ranking: string;
  masking_protocol: string;
  artifact_check: Record<string, unknown>;
  generated_at: string | null;
  data_quality: Record<string, Record<string, unknown>[]>;
  model_card: Record<string, unknown>;
  error_analysis: Record<string, Record<string, unknown>[]>;
}

export interface RefreshJob {
  job_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  top_k: number;
  max_users: number | null;
  logs: string[];
  result: Record<string, unknown> | null;
  error: string | null;
}
