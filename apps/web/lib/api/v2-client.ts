/**
 * CLARA API v2 Typed Client.
 *
 * Provides typed Axios/fetch wrapper with:
 * - CSRF token injection for mutating requests
 * - Profile context header injection (X-CLARA-Profile-Context)
 * - Optimistic concurrency (ETag / If-Match / base_version) handling
 * - Idempotency key injection
 * - Structured error normalization into ApiV2ClientError
 * - Cancellation via AbortSignal / AbortController
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";
import { getCsrfToken } from "@/lib/auth-store";
import { getActiveProfileId } from "@/lib/profile-context";

export const DEFAULT_TIMEOUT_MS = 60000;

export interface MessageMetadataDto {
  key: string;
  params?: Record<string, unknown>;
  severity?: "info" | "success" | "warning" | "error" | "critical" | string;
  action_target?: string | null;
}

export interface ApiV2ResponseEnvelopeDto<T> {
  data: T;
  meta?: Record<string, unknown> | null;
  message?: MessageMetadataDto | null;
  warnings?: MessageMetadataDto[];
}

export interface ApiV2ErrorEnvelopeDto {
  code: string;
  message_key?: string | null;
  message: string;
  params?: Record<string, unknown>;
  details?: unknown;
  safe_to_reapply?: boolean;
  current_version?: string | number | null;
  changed_fields?: string[];
}

export interface ApiV2Response<T> {
  data: T;
  meta?: Record<string, unknown> | null;
  message?: MessageMetadataDto | null;
  warnings?: MessageMetadataDto[];
  etag: string | null;
  status: number;
  headers: Record<string, string>;
}

export interface ApiV2RequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, unknown>;
  signal?: AbortSignal;
  timeout?: number;
  profileId?: string | null;
  etag?: string | number | null;
  ifMatch?: string | number | null;
  baseVersion?: string | number | null;
  idempotencyKey?: string | null;
  skipProfileContext?: boolean;
  skipCsrf?: boolean;
  withCredentials?: boolean;
}

export interface ApiV2RequestConfig extends ApiV2RequestOptions {
  url: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD" | "OPTIONS" | string;
  data?: unknown;
}

export type HomeSeverity =
  | "critical"
  | "urgent"
  | "high"
  | "warning"
  | "moderate"
  | "routine"
  | "normal"
  | "info";

export interface HomeProfileDto {
  id: string;
  display_name: string;
  kind?: "self" | "shared" | string;
  avatar_url?: string | null;
  relationship?: string | null;
}

export interface HomeTopActionDto {
  id: string;
  kind: "medication" | "visit" | "review" | "task" | "result" | string;
  title_key?: string | null;
  title?: string | null;
  description?: string | null;
  params?: Record<string, unknown>;
  href: string;
  severity: HomeSeverity | string;
  action_label?: string | null;
  secondary_action_label?: string | null;
  secondary_href?: string | null;
  source_ids?: string[];
  icon?: string | null;
}

export interface HomeTodayItemDto {
  id: string;
  kind: "medication" | "visit" | "task" | string;
  title: string;
  time?: string | null;
  due_time?: string | null;
  status?: "pending" | "completed" | "overdue" | "cancelled" | string;
  subtitle?: string | null;
  description?: string | null;
  href?: string | null;
  dosage?: string | null;
  instructions?: string | null;
  doctor_name?: string | null;
  location?: string | null;
  priority?: "normal" | "urgent" | "critical" | string;
}

export interface HomeRecentChangeDto {
  id: string;
  kind: "result" | "document" | "medication" | "timeline" | "measurement" | string;
  title: string;
  description?: string | null;
  timestamp: string;
  source_kind?:
    | "clinician"
    | "doctor"
    | "hospital"
    | "clinic"
    | "device"
    | "patient"
    | "self"
    | "imported"
    | "prescription"
    | "lab"
    | string;
  verification_state?:
    | "verified"
    | "self-reported"
    | "self_reported"
    | "imported"
    | "device"
    | "pending"
    | "unverified"
    | string;
  source_name?: string | null;
  href?: string | null;
}

export interface HomeAlertDto {
  id: string;
  kind?: "ddi" | "allergy" | "recall" | "critical" | "warning" | "info" | string;
  severity: "critical" | "warning" | "info" | "error" | string;
  title: string;
  message: string;
  href?: string | null;
  action_label?: string | null;
  dismissible?: boolean;
}

export interface HomeTrendCardDto {
  id: string;
  title: string;
  value?: string | number | null;
  unit?: string | null;
  status?: string | null;
}

export interface HomeIntegrationStateDto {
  last_sync_at?: string | null;
  has_connected_health?: boolean;
}

export interface HomeOverviewDto {
  profile?: HomeProfileDto | null;
  generated_at?: string | null;
  context_version?: string | null;
  top_action?: HomeTopActionDto | null;
  today: HomeTodayItemDto[];
  recent_changes: HomeRecentChangeDto[];
  alerts: HomeAlertDto[];
  trend_cards?: HomeTrendCardDto[];
  integration_state?: HomeIntegrationStateDto;
}

export interface HealthDemographicsDto {
  full_name?: string;
  date_of_birth?: string;
  gender?: "male" | "female" | "other" | string;
  blood_type?: "A+" | "A-" | "B+" | "B-" | "AB+" | "AB-" | "O+" | "O-" | "unknown" | string;
  phone_number?: string;
  address?: string;
  emergency_contact?: {
    name?: string;
    relationship?: string;
    phone?: string;
  };
  base_version?: string | number;
}

export interface HealthAllergyDto {
  id: string;
  substance: string;
  reaction?: string | null;
  severity?: "mild" | "moderate" | "severe" | "unknown" | string;
  verification_state?: string;
  source_kind?: string;
  source_name?: string;
  recorded_at?: string;
  base_version?: string | number;
}

export interface HealthConditionDto {
  id: string;
  name: string;
  clinical_status?: "active" | "recurrence" | "relapse" | "inactive" | "remission" | "resolved" | "unknown" | string;
  verification_status?: "confirmed" | "provisional" | "differential" | "unconfirmed" | "refuted" | string;
  onset_date?: string | null;
  notes?: string | null;
  source_kind?: string;
  source_name?: string;
  recorded_at?: string;
  base_version?: string | number;
}

export interface HealthMedicationCourseDto {
  id: string;
  name: string;
  generic_name?: string | null;
  dosage?: string | null;
  frequency?: string | null;
  instructions?: string | null;
  status: "active" | "completed" | "stopped" | "on_hold" | "draft" | string;
  start_date?: string | null;
  end_date?: string | null;
  prescribed_by?: string | null;
  source_kind?: string;
  verification_state?: string;
  safety_warnings?: string[];
  notes?: string | null;
  base_version?: string | number;
}

export interface HealthMeasurementDto {
  id: string;
  type: string;
  label?: string;
  value: string | number;
  unit: string;
  systolic?: number;
  diastolic?: number;
  recorded_at: string;
  source_kind?: string;
  source_name?: string;
  verification_state?: string;
  reference_range?: string | null;
  status?: "normal" | "low" | "high" | "critical" | string;
  notes?: string | null;
  base_version?: string | number;
}

export interface HealthRecentResultDto {
  id: string;
  test_name: string;
  category?: string | null;
  value: string | number;
  unit?: string | null;
  reference_range?: string | null;
  flag?: "normal" | "abnormal" | "critical_high" | "critical_low" | "high" | "low" | string;
  effective_at: string;
  source_name?: string | null;
  source_kind?: string;
  verification_state?: string;
  history?: Array<{
    effective_at: string;
    value: string | number;
    unit?: string | null;
    reference_range?: string | null;
    flag?: string;
  }>;
}

export interface HealthDocumentDto {
  id: string;
  title: string;
  kind?: "prescription" | "lab_report" | "discharge_summary" | "clinical_note" | "imaging" | "other" | string;
  file_url?: string;
  file_size?: number;
  mime_type?: string;
  recorded_at: string;
  source_name?: string;
  source_kind?: string;
  verification_state?: string;
  extracted_summary?: string | null;
  provenance?: {
    uploaded_by?: string;
    facility?: string;
    scanned_at?: string;
  };
}

export interface HealthConflictDto {
  id: string;
  domain: "medication" | "allergy" | "condition" | "measurement" | string;
  title: string;
  description: string;
  source_a: { label: string; value: string; date?: string };
  source_b: { label: string; value: string; date?: string };
  status: "unresolved" | "resolved" | "ignored" | string;
  detected_at?: string;
}

export interface CareTaskDto {
  id: string;
  title: string;
  due_date?: string | null;
  status: "pending" | "completed" | "overdue" | "in_progress" | string;
  priority?: "routine" | "urgent" | "high" | "normal" | string;
  category?: string | null;
  description?: string | null;
  assigned_to?: string | null;
  href?: string | null;
  completed_at?: string | null;
}

export interface CareVisitDocumentDto {
  id: string;
  title: string;
  file_url?: string;
  mime_type?: string;
  size?: number;
  recorded_at?: string;
  summary?: string;
}

export interface CareVisitDto {
  id: string;
  title: string;
  doctor_name?: string | null;
  specialty?: string | null;
  facility_name?: string | null;
  location?: string | null;
  scheduled_at: string;
  status: "scheduled" | "completed" | "cancelled" | "in_progress" | string;
  prep_status?: "not_started" | "in_progress" | "ready" | "completed" | string;
  visit_type?: string | null;
  notes?: string | null;
  reason_for_visit?: string | null;
  documents?: CareVisitDocumentDto[];
  document_count?: number;
  handoff_summary?: string | null;
  base_version?: string | number;
}

export interface VisitPrepPromptDto {
  id: string;
  visit_id?: string;
  title: string;
  description: string;
  urgency?: "normal" | "urgent" | "high" | string;
  action_label?: string;
  action_href: string;
  type?: "unanswered_questions" | "missing_records" | "recent_symptoms" | "medication_review" | string;
}

export interface CareSummaryDto {
  profile?: HomeProfileDto | null;
  upcoming_visits: CareVisitDto[];
  past_visits?: CareVisitDto[];
  prep_prompts: VisitPrepPromptDto[];
  active_tasks: CareTaskDto[];
  recent_symptom_checks?: Array<{
    id: string;
    checked_at: string;
    urgency: string;
    symptoms: string[];
    summary: string;
  }>;
  context_version?: string;
}

export interface VisitPrepRequestDto {
  visit_id?: string;
  purpose?: string;
  what_changed?: string;
  changes_since_last_visit?: string[];
  questions?: string[];
  goals?: string[];
  notes?: string;
  selected_document_ids?: string[];
}

export interface VisitPrepHandoffSummaryDto {
  visit_id?: string;
  purpose: string;
  summary: string;
  what_changed: string[];
  patient_questions: string[];
  patient_goals: string[];
  current_medications_summary?: string[];
  recent_vital_trends?: string[];
  created_at: string;
  share_url?: string;
  share_token?: string;
}

export type SymptomUrgencyLevel = "emergency" | "urgent" | "routine" | "pharmacist" | "self_care";

export interface SymptomCheckRequestDto {
  symptoms: string[];
  duration?: string;
  severity?: "mild" | "moderate" | "severe" | "critical" | string;
  red_flags?: string[];
  answers?: Record<string, string | boolean>;
  profile_id?: string | null;
  notes?: string;
  age_group?: "infant" | "child" | "adult" | "elderly" | string;
}

export interface SymptomCheckResultDto {
  urgency: SymptomUrgencyLevel | string;
  is_red_flag_emergency: boolean;
  title: string;
  explanation: string;
  care_navigation_guidance: string;
  recommended_actions: string[];
  clinician_handoff_summary: string;
  questions_for_doctor: string[];
  self_care_tips?: string[];
  when_to_seek_immediate_care: string[];
}

export interface MedicationsHubDto {
  medications: HealthMedicationCourseDto[];
  cabinet?: Array<{
    id: string;
    name: string;
    form?: string;
    strength?: string;
    quantity?: number;
    expiry_date?: string;
    notes?: string;
  }>;
  safety_alerts?: Array<{
    id: string;
    severity: "critical" | "warning" | "info" | string;
    title: string;
    description: string;
    medication_ids?: string[];
  }>;
}

export interface MedicationSafetyCheckRequestDto {
  medication_ids?: string[];
  new_medication_name?: string;
  allergies?: string[];
  conditions?: string[];
}

export interface MedicationSafetyCheckResultDto {
  has_critical_ddi: boolean;
  safety_score?: number;
  interactions: Array<{
    id?: string;
    severity: "critical" | "warning" | "info" | string;
    title: string;
    description: string;
    recommendation?: string;
    affected_medications?: string[];
  }>;
  allergy_warnings?: Array<{
    substance: string;
    severity: string;
    description: string;
  }>;
  contraindications?: Array<{
    condition: string;
    description: string;
  }>;
}

export interface HealthSummaryDto {
  profile?: HomeProfileDto | null;
  demographics?: HealthDemographicsDto;
  current: {
    allergies: HealthAllergyDto[];
    conditions: HealthConditionDto[];
    medications: HealthMedicationCourseDto[];
    important_measurements: HealthMeasurementDto[];
  };
  recent_results: HealthRecentResultDto[];
  documents: HealthDocumentDto[];
  completeness?: {
    missing_categories: string[];
  };
  conflicts: HealthConflictDto[];
  context_version?: string;
}

export interface HealthTimelineRevisionDto {
  id: string;
  modified_at: string;
  modified_by?: string;
  summary: string;
  previous_value?: string;
  new_value?: string;
}

export interface HealthTimelineEventDto {
  id: string;
  kind:
    | "medication"
    | "medication_change"
    | "symptom"
    | "condition"
    | "visit"
    | "result"
    | "measurement"
    | "document"
    | string;
  effective_at: string;
  recorded_at?: string;
  title: string;
  summary?: string;
  state?:
    | "confirmed"
    | "user-reported"
    | "user_reported"
    | "imported"
    | "device"
    | "unconfirmed"
    | "stopped"
    | "conflict"
    | "stale"
    | string;
  source?: {
    kind?: string;
    name?: string;
    label?: string;
    recorder?: string;
    recorded_at?: string;
    verification_state?: string;
  };
  episode_id?: string | null;
  detail_href?: string | null;
  revisions?: HealthTimelineRevisionDto[];
}

export interface HealthTimelineResponseDto {
  items: HealthTimelineEventDto[];
  next_cursor?: string | null;
  total?: number;
}

export interface HealthTimelineParams {
  cursor?: string | null;
  from?: string | null;
  to?: string | null;
  period?: "recent" | "month" | "year" | "all" | string;
  types?: string[];
  search?: string;
  limit?: number;
}

export type AskActionType = "text" | "camera" | "file" | "voice";

export interface EntryContextDto {
  kind: "global" | "result" | "medication" | "visit" | "timeline_period" | "document" | string;
  resource_id?: string | null;
  label?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ConsumerAskAttachmentDto {
  id?: string;
  name?: string;
  file_type?: string;
  mime_type?: string;
  size?: number;
  url?: string;
  data_url?: string;
}

export interface ConsumerAskRequest {
  text: string;
  conversation_id?: string | null;
  attachments?: Array<string | ConsumerAskAttachmentDto>;
  entry_context?: EntryContextDto | null;
  ui_language?: "vi" | "en" | string;
}

export interface ConsumerAnswerActionDto {
  id: string;
  label: string;
  action_type?: "navigate" | "reminder" | "call" | "log" | "link" | string;
  target?: string | null;
  description?: string | null;
  params?: Record<string, unknown>;
}

export interface ConsumerAnswerSectionDto {
  title: string;
  content: string;
}

export interface ConsumerPersonalEvidenceDto {
  id: string;
  resource_id?: string;
  resource_type?:
    | "medication"
    | "allergy"
    | "condition"
    | "measurement"
    | "result"
    | "document"
    | "visit"
    | string;
  title: string;
  snippet?: string;
  effective_at?: string;
  source_name?: string;
  source_kind?: string;
  state?:
    | "confirmed"
    | "user_reported"
    | "user-reported"
    | "unconfirmed"
    | "imported"
    | "device"
    | "conflict"
    | string;
  verification_state?: string;
}

export interface ConsumerExternalSourceDto {
  id: string;
  title: string;
  publisher?: string;
  url?: string;
  year?: string | number;
  snippet?: string;
  doi?: string;
}

export interface ConsumerUnknownItemDto {
  id?: string;
  missing_factor: string;
  why_it_matters?: string;
  category?: "missing_data" | "clinical_uncertainty" | "unverified_assumption" | string;
}

export type ConsumerUnknownDto = string | ConsumerUnknownItemDto;

export type SafetyUrgency = "none" | "routine" | "soon" | "urgent" | "emergency";

export interface ConsumerSafetyGuidanceDto {
  urgency: SafetyUrgency | string;
  deterministic_floor_applied?: boolean;
  guidance?: string;
  action_required?: string;
  red_flags?: string[];
}

export interface WriteProposalDto {
  id: string;
  kind: "medication" | "allergy" | "condition" | "measurement" | "task" | "visit" | string;
  title: string;
  summary?: string;
  status?: "pending" | "confirmed" | "rejected" | "edited" | string;
  data?: Record<string, unknown>;
  provenance?: {
    source?: string;
    confidence?: number;
    extracted_at?: string;
  };
}

export type CaptureCategory =
  | "medication"
  | "measurement"
  | "condition"
  | "allergy"
  | "document"
  | "visit"
  | "vital"
  | "lab"
  | "clinical_note"
  | "general"
  | string;

export type CandidateReviewStatus =
  | "pending"
  | "accepted"
  | "confirmed"
  | "rejected"
  | "edited"
  | string;

export interface CaptureCandidateV2 {
  id: string;
  category: CaptureCategory;
  field_name: string;
  display_name?: string | null;
  value: string | number | Record<string, unknown>;
  original_value?: string | number | Record<string, unknown>;
  unit?: string | null;
  status: CandidateReviewStatus;
  confidence?: number | null;
  ocr_confidence?: number | null;
  has_uncertainty?: boolean;
  uncertainty_reason?: string | null;
  source_snippet?: string | null;
  source_page?: number | null;
  source_span?: {
    start?: number;
    end?: number;
    text?: string;
  } | null;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
    page?: number;
  } | null;
  metadata?: Record<string, unknown>;
  missing_critical_fields?: string[];
  security_findings?: string[];
  schema_version?: string;
  artifact_id?: string | null;
}

export interface CaptureArtifactV2 {
  id: string;
  media_type: string;
  filename: string;
  file_size?: number;
  file_url?: string;
  checksum?: string;
  access_token?: string;
  access_expires_at?: string;
}

export interface CaptureSessionV2 {
  id: string;
  input_kind?:
    | "camera"
    | "upload"
    | "medicine_scan"
    | "voice"
    | "manual"
    | "text"
    | "medication_label"
    | "visit_document"
    | string;
  status: "draft" | "processing" | "ready" | "committed" | "abandoned" | "failed" | string;
  created_at?: string;
  expires_at?: string;
  candidates: CaptureCandidateV2[];
  artifacts?: CaptureArtifactV2[];
  emergency?: boolean;
  persisted?: boolean;
  message?: string;
}

export interface CreateCaptureSessionRequest {
  input_kind:
    | "camera"
    | "upload"
    | "medicine_scan"
    | "voice"
    | "manual"
    | "text"
    | "medication_label"
    | "visit_document"
    | string;
  locale?: "vi" | "en" | string;
  text?: string;
  entry_context?: EntryContextDto | null;
  metadata?: Record<string, unknown>;
}

export interface ReviewCaptureCandidateRequest {
  action: "accept" | "confirm" | "reject" | "edit";
  value?: string | number | Record<string, unknown>;
  reason?: string;
  accept_normalization?: boolean;
}

export interface CommitCaptureSessionRequest {
  candidate_ids?: string[];
  target_section?:
    | "medications"
    | "measurements"
    | "conditions"
    | "allergies"
    | "timeline"
    | "general"
    | string;
  notes?: string;
}

export interface CommitCaptureSessionResponse {
  success: boolean;
  committed_count: number;
  target_section?: string;
  redirect_url?: string;
  message?: string;
  created_ids?: {
    medication_ids?: string[];
    measurement_ids?: string[];
    condition_ids?: string[];
    allergy_ids?: string[];
    document_ids?: string[];
    event_ids?: string[];
  };
}

export interface ConsumerDisclosureDto {
  used_personal_context: boolean;
  data_classes: string[];
  explanation?: string;
}

export interface ConsumerAnswerEnvelope {
  answer: {
    main_message: string;
    actions?: ConsumerAnswerActionDto[];
    sections?: ConsumerAnswerSectionDto[];
  };
  personal_evidence?: ConsumerPersonalEvidenceDto[];
  external_sources?: ConsumerExternalSourceDto[];
  unknowns?: ConsumerUnknownDto[];
  safety?: ConsumerSafetyGuidanceDto;
  write_proposals?: WriteProposalDto[];
  disclosure?: ConsumerDisclosureDto;
  conversation_id?: string;
  created_at?: string;
}

export interface ConsumerAskStreamHandlers {
  onStart?: () => void;
  onToken?: (token: string) => void;
  onMainMessage?: (text: string) => void;
  onSafety?: (safety: ConsumerSafetyGuidanceDto) => void;
  onEvidence?: (evidence: {
    personal_evidence?: ConsumerPersonalEvidenceDto[];
    external_sources?: ConsumerExternalSourceDto[];
    disclosure?: ConsumerDisclosureDto;
  }) => void;
  onProposals?: (proposals: WriteProposalDto[]) => void;
  onUnknowns?: (unknowns: ConsumerUnknownDto[]) => void;
  onDone?: (envelope: ConsumerAnswerEnvelope) => void;
  onError?: (error: ApiV2ClientError | Error | string) => void;
}

export interface YouEmergencyCardSummaryDto {
  id?: string;
  blood_type?: string | null;
  allergies_count: number;
  conditions_count: number;
  medications_count: number;
  medical_alerts: string[];
  emergency_contact?: {
    name: string;
    phone: string;
    relationship?: string;
  } | null;
  is_configured: boolean;
  last_updated?: string;
}

export interface FamilySharingSummaryDto {
  active_grants_count: number;
  received_grants_count: number;
  pending_invites_count: number;
  members: Array<{
    id: string;
    name: string;
    relationship: string;
    role: string;
    avatar_url?: string;
    status: "active" | "pending" | "revoked";
  }>;
}

export interface PrivacyAiSummaryDto {
  data_classes_used: string[];
  ai_features_enabled: boolean;
  cot_disabled: boolean;
  retention_policy_days: number;
  consent_status: "granted" | "pending" | "revoked" | "not_started" | string;
  last_consent_at?: string;
}

export interface IntegrationSourceSummaryDto {
  id: string;
  name: "health_connect" | "apple_health" | "garmin" | "fitbit" | string;
  title: string;
  connected: boolean;
  sync_enabled: boolean;
  last_sync_at?: string | null;
  status: "active" | "error" | "disconnected" | "syncing" | string;
  error_message?: string | null;
}

export interface IntegrationsSummaryDto {
  total_connected: number;
  sources: IntegrationSourceSummaryDto[];
}

export interface ProfessionalModeDto {
  eligible: boolean;
  role: string;
  active_workspace?: string;
}

export interface YouOverviewDto {
  profile?: HomeProfileDto | null;
  demographics?: HealthDemographicsDto;
  emergency_card: YouEmergencyCardSummaryDto;
  family_sharing: FamilySharingSummaryDto;
  privacy_ai: PrivacyAiSummaryDto;
  integrations: IntegrationsSummaryDto;
  professional_mode: ProfessionalModeDto;
  notifications?: {
    unread_count: number;
    preferences: NotificationPreferencesDto;
  };
}

export interface ProfileDetailsDto {
  id: string;
  display_name: string;
  full_name?: string;
  email?: string | null;
  phone?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  blood_type?: string | null;
  address?: string | null;
  emergency_contact?: {
    name: string;
    phone: string;
    relationship?: string;
  } | null;
  allergies?: Array<{
    id: string;
    name: string;
    severity?: string;
    reaction?: string;
    is_critical?: boolean;
  }>;
  conditions?: Array<{
    id: string;
    name: string;
    status?: string;
    is_critical?: boolean;
  }>;
  medications?: Array<{
    id: string;
    name: string;
    dose?: string;
    is_critical?: boolean;
  }>;
  medical_alerts?: string[];
  emergency_card_included_fields?: {
    allergies: boolean;
    current_medications: boolean;
    conditions: boolean;
    blood_type: boolean;
    emergency_contact: boolean;
  };
}

export interface EmergencyCardDto {
  id?: string;
  profile_id?: string;
  blood_type?: string | null;
  allergies: Array<{ name: string; severity?: string; reaction?: string }>;
  current_medications: Array<{ name: string; dose?: string }>;
  conditions: Array<{ name: string; status?: string }>;
  emergency_contact?: {
    name: string;
    phone: string;
    relationship?: string;
  } | null;
  medical_alerts?: string[];
  included_fields: {
    allergies: boolean;
    current_medications: boolean;
    conditions: boolean;
    blood_type: boolean;
    emergency_contact: boolean;
  };
  disclaimer?: Record<string, string>;
  last_updated?: string;
}

export type SharingGrantCategory =
  | "medications"
  | "allergies"
  | "lab_results"
  | "visits"
  | "timeline";

export type SharingGrantAction = "view" | "add_observation" | "complete_task";

export interface SharingGrantDto {
  id: string;
  grantee_name: string;
  grantee_relationship: string;
  grantee_email?: string | null;
  grantee_role?: string;
  categories: SharingGrantCategory[];
  allowed_actions: SharingGrantAction[];
  purpose: "care_coordination" | "visit_support" | "emergency_only" | "full_access" | string;
  purpose_description?: string;
  duration_days?: number;
  created_at: string;
  expires_at: string;
  status: "active" | "revoked" | "expired" | string;
  token?: string;
}

export interface SharingGrantRequestDto {
  grantee_name: string;
  grantee_relationship: string;
  grantee_email?: string;
  categories: SharingGrantCategory[];
  allowed_actions: SharingGrantAction[];
  purpose: string;
  duration_days?: number;
  custom_expires_at?: string;
}

export interface SharingAccessLogDto {
  id: string;
  actor_name: string;
  actor_role: string;
  actor_relationship?: string;
  action: string;
  object_type: string;
  accessed_at: string;
  outcome: "allowed" | "denied" | "failed" | string;
  ip_address?: string;
}

export interface SharingOverviewDto {
  grants: SharingGrantDto[];
  received_grants: SharingGrantDto[];
  access_logs: SharingAccessLogDto[];
}

export interface AiTransparencyDto {
  data_classes_used: Array<{
    key: string;
    name: string;
    purpose: string;
    sensitive: boolean;
  }>;
  retention_policy: {
    days: number;
    description: string;
    auto_delete_enabled: boolean;
  };
  cot_zero_disclosure: {
    operates_without_cot: boolean;
    description: string;
    verified_guardrails: string[];
  };
  ai_feature_controls: {
    symptom_insights_enabled: boolean;
    visit_prep_suggestions_enabled: boolean;
    medication_safety_ai_enabled: boolean;
    search_summaries_enabled: boolean;
  };
  consent_status: {
    version: string;
    granted_at?: string;
    status: "granted" | "pending" | "withdrawn" | string;
    requires_reconsent: boolean;
    purposes: Array<{
      purpose: string;
      label: string;
      granted: boolean;
      locked?: boolean;
    }>;
  };
}

export interface AiPreferencesDto {
  symptom_insights_enabled?: boolean;
  visit_prep_suggestions_enabled?: boolean;
  medication_safety_ai_enabled?: boolean;
  search_summaries_enabled?: boolean;
}

export interface ConnectedHealthCategoryPermissionsDto {
  steps: boolean;
  heart_rate: boolean;
  blood_pressure: boolean;
  sleep: boolean;
  blood_glucose: boolean;
  oxygen_saturation: boolean;
}

export interface ConnectedHealthSourceDto {
  id: string;
  name: "health_connect" | "apple_health" | "garmin" | "fitbit" | string;
  title: string;
  description: string;
  connected: boolean;
  sync_enabled: boolean;
  last_sync_at: string | null;
  status: "active" | "disconnected" | "syncing" | "error" | string;
  error_message?: string | null;
  recovery_guidance?: string | null;
  category_permissions: ConnectedHealthCategoryPermissionsDto;
}

export interface ConnectedHealthSourcesDto {
  sources: ConnectedHealthSourceDto[];
  last_global_sync_at?: string | null;
}

export interface NotificationCategoryPreferencesDto {
  medications: boolean;
  visits: boolean;
  review_items: boolean;
  safety_alerts: boolean;
  journey_milestones?: boolean;
  family_activity?: boolean;
}

export interface NotificationPreferencesDto {
  categories: NotificationCategoryPreferencesDto;
  channels: {
    push: boolean;
    email: boolean;
    in_app: boolean;
  };
  quiet_hours: {
    enabled: boolean;
    start_time: string;
    end_time: string;
  };
}

export interface ActiveSessionDto {
  id: string;
  device_name: string;
  device_type: "desktop" | "mobile" | "tablet" | "browser";
  platform: string;
  browser?: string;
  ip_address: string;
  location: string;
  last_active_at: string;
  is_current: boolean;
}

export interface SecuritySettingsDto {
  mfa_enabled: boolean;
  mfa_method?: "totp" | "sms" | "security_key";
  mfa_configured_at?: string | null;
  inactivity_timeout_minutes: number;
  new_login_alerts: boolean;
  reauth_for_sensitive: boolean;
  active_sessions: ActiveSessionDto[];
}

export function parseSseFrame(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

export class ApiV2ClientError extends Error {
  readonly code: string;
  readonly messageKey: string | null;
  readonly params: Record<string, unknown>;
  readonly details: unknown;
  readonly safeToReapply: boolean;
  readonly status: number;
  readonly currentVersion: string | number | null;
  readonly changedFields: string[];
  readonly isConflict: boolean;
  readonly isPreconditionFailed: boolean;
  readonly isUnauthorized: boolean;
  readonly isForbidden: boolean;
  readonly isNotFound: boolean;
  readonly isValidationError: boolean;
  readonly isRateLimited: boolean;
  readonly isCancelled: boolean;
  readonly isNetworkError: boolean;
  readonly rawError?: unknown;

  constructor(options: {
    message: string;
    code?: string;
    messageKey?: string | null;
    params?: Record<string, unknown>;
    details?: unknown;
    safeToReapply?: boolean;
    status?: number;
    currentVersion?: string | number | null;
    changedFields?: string[];
    isCancelled?: boolean;
    isNetworkError?: boolean;
    rawError?: unknown;
  }) {
    super(options.message);
    this.name = "ApiV2ClientError";
    this.code = options.code ?? "UNKNOWN_ERROR";
    this.messageKey = options.messageKey ?? null;
    this.params = options.params ?? {};
    this.details = options.details;
    this.safeToReapply = options.safeToReapply ?? false;
    this.status = options.status ?? 0;
    this.currentVersion = options.currentVersion ?? null;
    this.changedFields = options.changedFields ?? [];
    this.isCancelled = options.isCancelled ?? false;
    this.isNetworkError = options.isNetworkError ?? false;

    this.isConflict =
      this.status === 409 ||
      this.code === "state_conflict" ||
      this.code === "idempotency_conflict";
    this.isPreconditionFailed =
      this.status === 412 || this.code === "precondition_failed" || this.code === "state_conflict";
    this.isUnauthorized = this.status === 401 || this.code === "unauthorized";
    this.isForbidden = this.status === 403 || this.code === "forbidden";
    this.isNotFound = this.status === 404 || this.code === "not_found";
    this.isValidationError = this.status === 422 || this.code === "validation_error";
    this.isRateLimited = this.status === 429 || this.code === "rate_limited";
    this.rawError = options.rawError;
  }
}

export function formatEtag(version: string | number, weak = false): string {
  const clean = String(version).trim().replace(/^W\//, "").replace(/^"|"$/g, "");
  return weak ? `W/"${clean}"` : `"${clean}"`;
}

export function parseEtag(etag: string | null | undefined): string | null {
  if (!etag) return null;
  const clean = etag.trim().replace(/^W\//, "").replace(/^"|"$/g, "");
  return clean || null;
}

export function resolveApiV2BaseUrl(): string {
  if (typeof window === "undefined") {
    if (process.env.NEXT_PUBLIC_API_V2_URL?.trim()) {
      return process.env.NEXT_PUBLIC_API_V2_URL.trim();
    }
    const legacy = process.env.NEXT_PUBLIC_API_URL?.trim();
    if (legacy) {
      return legacy.replace(/\/api\/v1\/?$/, "/api/v2");
    }
    return "http://localhost:8100/api/v2";
  }

  const fallback = `${window.location.origin}/api/v2`;
  const configured =
    process.env.NEXT_PUBLIC_API_V2_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim()?.replace(/\/api\/v1\/?$/, "/api/v2");

  if (!configured) return fallback;
  const allowCrossOrigin = process.env.NEXT_PUBLIC_API_ALLOW_CROSS_ORIGIN === "true";
  try {
    const resolved = new URL(configured, window.location.origin);
    if (!allowCrossOrigin && resolved.origin !== window.location.origin) {
      return fallback;
    }
    return resolved.toString();
  } catch {
    return fallback;
  }
}

function isMutatingMethod(method?: string): boolean {
  const m = String(method ?? "GET").toUpperCase();
  return m === "POST" || m === "PUT" || m === "PATCH" || m === "DELETE";
}

function normalizeGatewayPayload(rawValue: string): string | null {
  const raw = String(rawValue ?? "").trim();
  if (!raw) return null;
  const lowered = raw.toLowerCase();
  const looksLikeHtml =
    lowered.includes("<html") || lowered.includes("<!doctype html") || lowered.includes("</html>");
  if (!looksLikeHtml) return null;
  if (lowered.includes("502 bad gateway")) {
    return "Dịch vụ tạm thời gián đoạn (502). Vui lòng thử lại sau ít phút.";
  }
  if (lowered.includes("503 service unavailable")) {
    return "Dịch vụ tạm thời không khả dụng (503). Vui lòng thử lại sau ít phút.";
  }
  if (lowered.includes("504 gateway timeout")) {
    return "Hết thời gian chờ phản hồi từ máy chủ (504). Vui lòng thử lại.";
  }
  return "Hệ thống trả về phản hồi không hợp lệ. Vui lòng thử lại.";
}

export function normalizeApiV2Error(error: unknown): ApiV2ClientError {
  if (error instanceof ApiV2ClientError) {
    return error;
  }

  // 1. Cancellation checks
  if (
    axios.isCancel(error) ||
    (error as { name?: string })?.name === "AbortError" ||
    (error as { code?: string })?.code === "ERR_CANCELED"
  ) {
    return new ApiV2ClientError({
      code: "CANCELLED",
      messageKey: "errors.request_cancelled",
      message: "Yêu cầu đã bị hủy.",
      isCancelled: true,
      status: 0,
      rawError: error,
    });
  }

  // 2. Axios network / timeout errors without HTTP response
  if (axios.isAxiosError(error) && !error.response) {
    const isTimeout = error.code === "ECONNABORTED" || error.message.includes("timeout");
    return new ApiV2ClientError({
      code: isTimeout ? "TIMEOUT" : "NETWORK_ERROR",
      messageKey: isTimeout ? "errors.request_timeout" : "errors.network_error",
      message: isTimeout
        ? "Yêu cầu vượt quá thời gian phản hồi cho phép. Vui lòng thử lại."
        : "Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối mạng.",
      isNetworkError: true,
      status: 0,
      rawError: error,
    });
  }

  // 3. HTTP response errors
  if (axios.isAxiosError(error) && error.response) {
    const status = error.response.status;
    const data = error.response.data as
      | ApiV2ErrorEnvelopeDto
      | { detail?: unknown; message?: string }
      | string
      | undefined;

    let code = "HTTP_ERROR";
    let messageKey: string | null = null;
    let message = `Lỗi máy chủ (${status})`;
    let params: Record<string, unknown> = {};
    let details: unknown = undefined;
    let safeToReapply = false;
    let currentVersion: string | number | null = null;
    let changedFields: string[] = [];

    // Default code / messageKey mappings by status
    if (status === 401) {
      code = "unauthorized";
      messageKey = "errors.unauthorized";
      message = "Phiên đăng nhập đã hết hạn hoặc không hợp lệ.";
    } else if (status === 403) {
      code = "forbidden";
      messageKey = "errors.forbidden";
      message = "Bạn không có quyền thực hiện thao tác này.";
    } else if (status === 404) {
      code = "not_found";
      messageKey = "errors.not_found";
      message = "Không tìm thấy tài nguyên yêu cầu.";
    } else if (status === 409) {
      code = "state_conflict";
      messageKey = "errors.state_conflict";
      message = "Dữ liệu đã bị thay đổi bởi thao tác khác.";
    } else if (status === 412) {
      code = "state_conflict";
      messageKey = "errors.state_conflict";
      message = "Phiên bản dữ liệu không khớp với máy chủ.";
    } else if (status === 422) {
      code = "validation_error";
      messageKey = "errors.validation_error";
      message = "Dữ liệu gửi lên không đúng định dạng.";
    } else if (status === 429) {
      code = "rate_limited";
      messageKey = "errors.rate_limited";
      message = "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.";
    } else if (status >= 500) {
      code = "server_error";
      messageKey = "errors.server_error";
      message = "Máy chủ gặp sự cố nội bộ. Vui lòng thử lại sau.";
    }

    if (typeof data === "string") {
      const gw = normalizeGatewayPayload(data);
      if (gw) message = gw;
    } else if (data && typeof data === "object") {
      // Structured ApiV2ErrorEnvelope
      if ("code" in data && typeof data.code === "string") {
        code = data.code;
        if (typeof data.message === "string" && data.message.trim()) {
          message = data.message;
        }
        if (typeof data.message_key === "string") {
          messageKey = data.message_key;
        }
        if (data.params && typeof data.params === "object") {
          params = data.params;
        }
        details = data.details;
        safeToReapply = Boolean(data.safe_to_reapply);
        currentVersion = data.current_version ?? null;
        if (Array.isArray(data.changed_fields)) {
          changedFields = data.changed_fields;
        }
      } else if ("detail" in data && data.detail !== undefined) {
        if (typeof data.detail === "string" && data.detail.trim()) {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          code = "validation_error";
          messageKey = "errors.validation_failed";
          message = "Dữ liệu yêu cầu không hợp lệ.";
          details = data.detail;
        } else if (typeof data.detail === "object" && data.detail !== null) {
          const detailObj = data.detail as Record<string, unknown>;
          if (typeof detailObj.code === "string") code = detailObj.code;
          if (typeof detailObj.message === "string") message = detailObj.message;
          if (typeof detailObj.message_key === "string") messageKey = detailObj.message_key;
          if (detailObj.current_version !== undefined) {
            currentVersion = detailObj.current_version as string | number;
          }
          if (Array.isArray(detailObj.changed_fields)) {
            changedFields = detailObj.changed_fields as string[];
          }
          safeToReapply = Boolean(detailObj.safe_to_reapply);
          details = detailObj.details ?? detailObj;
        }
      } else if ("message" in data && typeof data.message === "string") {
        message = data.message;
      }
    }

    return new ApiV2ClientError({
      code,
      messageKey,
      message,
      params,
      details,
      safeToReapply,
      status,
      currentVersion,
      changedFields,
      rawError: error,
    });
  }

  // 4. Generic JS / fallback error
  const msg = error instanceof Error ? error.message : String(error || "Unknown error");
  return new ApiV2ClientError({
    code: "UNKNOWN_ERROR",
    message: msg,
    rawError: error,
  });
}

export class ApiV2Client {
  private readonly client: AxiosInstance;
  readonly baseUrl: string;

  constructor(customBaseUrl?: string, customAxios?: AxiosInstance) {
    this.baseUrl = customBaseUrl ?? resolveApiV2BaseUrl();
    this.client =
      customAxios ??
      axios.create({
        baseURL: this.baseUrl,
        timeout: DEFAULT_TIMEOUT_MS,
        withCredentials: true,
      });
  }

  private buildHeaders(
    method: string,
    options?: ApiV2RequestOptions,
  ): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(options?.headers ?? {}),
    };

    // 1. Profile context injection (X-CLARA-Profile-Context)
    if (!options?.skipProfileContext) {
      const targetProfileId = options?.profileId ?? getActiveProfileId();
      if (targetProfileId && !headers["X-CLARA-Profile-Context"]) {
        headers["X-CLARA-Profile-Context"] = targetProfileId;
      }
    }

    // 2. CSRF Token injection
    if (isMutatingMethod(method) && !options?.skipCsrf) {
      const csrf = getCsrfToken();
      if (csrf && !headers["X-CSRF-Token"]) {
        headers["X-CSRF-Token"] = csrf;
      }
    }

    // 3. ETag / base version precondition (If-Match)
    const etagCandidate = options?.etag ?? options?.ifMatch ?? options?.baseVersion;
    if (etagCandidate !== undefined && etagCandidate !== null && !headers["If-Match"]) {
      headers["If-Match"] = formatEtag(etagCandidate);
    }

    // 4. Idempotency Key
    if (options?.idempotencyKey && !headers["Idempotency-Key"]) {
      headers["Idempotency-Key"] = options.idempotencyKey;
    }

    return headers;
  }

  async request<T>(config: ApiV2RequestConfig): Promise<ApiV2Response<T>> {
    const method = (config.method ?? "GET").toUpperCase();
    const headers = this.buildHeaders(method, config);

    const axiosConfig: AxiosRequestConfig = {
      url: config.url,
      method,
      data: config.data,
      params: config.params,
      headers,
      signal: config.signal,
      timeout: config.timeout ?? DEFAULT_TIMEOUT_MS,
      withCredentials: config.withCredentials ?? true,
    };

    try {
      const res: AxiosResponse = await this.client.request(axiosConfig);
      const rawEtag = res.headers?.etag || res.headers?.ETag;
      const normalizedEtag = parseEtag(typeof rawEtag === "string" ? rawEtag : null);

      const headerMap: Record<string, string> = {};
      if (res.headers && typeof res.headers === "object") {
        for (const [k, v] of Object.entries(res.headers)) {
          if (v !== undefined && v !== null) {
            headerMap[k.toLowerCase()] = String(v);
          }
        }
      }

      // Check if response is wrapped in ApiV2ResponseEnvelopeDto
      const body = res.data;
      if (body && typeof body === "object" && "data" in body) {
        const envelope = body as ApiV2ResponseEnvelopeDto<T>;
        return {
          data: envelope.data,
          meta: envelope.meta,
          message: envelope.message,
          warnings: envelope.warnings,
          etag: normalizedEtag,
          status: res.status,
          headers: headerMap,
        };
      }

      return {
        data: body as T,
        meta: null,
        message: null,
        warnings: [],
        etag: normalizedEtag,
        status: res.status,
        headers: headerMap,
      };
    } catch (err) {
      throw normalizeApiV2Error(err);
    }
  }

  async get<T>(url: string, options?: ApiV2RequestOptions): Promise<ApiV2Response<T>> {
    return this.request<T>({ ...options, url, method: "GET" });
  }

  async post<T>(
    url: string,
    data?: unknown,
    options?: ApiV2RequestOptions,
  ): Promise<ApiV2Response<T>> {
    return this.request<T>({ ...options, url, method: "POST", data });
  }

  async put<T>(
    url: string,
    data?: unknown,
    options?: ApiV2RequestOptions,
  ): Promise<ApiV2Response<T>> {
    return this.request<T>({ ...options, url, method: "PUT", data });
  }

  async patch<T>(
    url: string,
    data?: unknown,
    options?: ApiV2RequestOptions,
  ): Promise<ApiV2Response<T>> {
    return this.request<T>({ ...options, url, method: "PATCH", data });
  }

  async delete<T>(url: string, options?: ApiV2RequestOptions): Promise<ApiV2Response<T>> {
    return this.request<T>({ ...options, url, method: "DELETE" });
  }

  async fetchData<T>(url: string, options?: ApiV2RequestOptions): Promise<T> {
    const res = await this.get<T>(url, options);
    return res.data;
  }

  async getHome(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<HomeOverviewDto> {
    const res = await this.get<HomeOverviewDto>("/home", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async getHealthSummary(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<HealthSummaryDto> {
    const res = await this.get<HealthSummaryDto>("/health/summary", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async getHealthTimeline(
    params?: HealthTimelineParams,
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<HealthTimelineResponseDto> {
    const queryParams: Record<string, unknown> = {
      ...(options?.params ?? {}),
    };
    if (params?.cursor) queryParams.cursor = params.cursor;
    if (params?.from) queryParams.from = params.from;
    if (params?.to) queryParams.to = params.to;
    if (params?.period) queryParams.period = params.period;
    if (params?.types && params.types.length > 0) {
      queryParams.types = params.types.join(",");
    }
    if (params?.search) queryParams.search = params.search;
    if (params?.limit !== undefined) queryParams.limit = params.limit;

    const res = await this.get<HealthTimelineResponseDto>("/health/timeline", {
      ...options,
      params: queryParams,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateDemographics(
    data: Partial<HealthDemographicsDto>,
    options?: ApiV2RequestOptions,
  ): Promise<HealthDemographicsDto> {
    const res = await this.patch<HealthDemographicsDto>("/health/demographics", data, {
      ...options,
      baseVersion: data.base_version ?? options?.baseVersion,
    });
    return res.data;
  }

  async addAllergy(
    data: Omit<HealthAllergyDto, "id">,
    options?: ApiV2RequestOptions,
  ): Promise<HealthAllergyDto> {
    const res = await this.post<HealthAllergyDto>("/health/allergies", data, options);
    return res.data;
  }

  async updateAllergy(
    id: string,
    data: Partial<HealthAllergyDto>,
    options?: ApiV2RequestOptions,
  ): Promise<HealthAllergyDto> {
    const res = await this.patch<HealthAllergyDto>(`/health/allergies/${id}`, data, {
      ...options,
      baseVersion: data.base_version ?? options?.baseVersion,
    });
    return res.data;
  }

  async deleteAllergy(
    id: string,
    options?: ApiV2RequestOptions,
  ): Promise<{ success: boolean }> {
    const res = await this.delete<{ success: boolean }>(`/health/allergies/${id}`, options);
    return res.data;
  }

  async addCondition(
    data: Omit<HealthConditionDto, "id">,
    options?: ApiV2RequestOptions,
  ): Promise<HealthConditionDto> {
    const res = await this.post<HealthConditionDto>("/health/conditions", data, options);
    return res.data;
  }

  async updateCondition(
    id: string,
    data: Partial<HealthConditionDto>,
    options?: ApiV2RequestOptions,
  ): Promise<HealthConditionDto> {
    const res = await this.patch<HealthConditionDto>(`/health/conditions/${id}`, data, {
      ...options,
      baseVersion: data.base_version ?? options?.baseVersion,
    });
    return res.data;
  }

  async deleteCondition(
    id: string,
    options?: ApiV2RequestOptions,
  ): Promise<{ success: boolean }> {
    const res = await this.delete<{ success: boolean }>(`/health/conditions/${id}`, options);
    return res.data;
  }

  async addMeasurement(
    data: Omit<HealthMeasurementDto, "id">,
    options?: ApiV2RequestOptions,
  ): Promise<HealthMeasurementDto> {
    const res = await this.post<HealthMeasurementDto>("/health/measurements", data, options);
    return res.data;
  }

  async ask(
    request: ConsumerAskRequest,
    options?: ApiV2RequestOptions,
  ): Promise<ConsumerAnswerEnvelope> {
    const res = await this.post<ConsumerAnswerEnvelope>("/ask", request, options);
    return res.data;
  }

  async streamAsk(
    request: ConsumerAskRequest,
    handlers: ConsumerAskStreamHandlers,
    options?: ApiV2RequestOptions,
  ): Promise<void> {
    const headers = this.buildHeaders("POST", {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "Cache-Control": "no-cache",
        ...(options?.headers ?? {}),
      },
    });

    const streamUrl = `${this.baseUrl.replace(/\/$/, "")}/ask/stream`;

    try {
      const response = await fetch(streamUrl, {
        method: "POST",
        headers,
        credentials: options?.withCredentials === false ? "same-origin" : "include",
        body: JSON.stringify(request),
        signal: options?.signal,
      });

      if (!response.ok || !response.body) {
        // Fallback to non-streaming POST /ask if stream route is not mounted / 404 / 405
        if (response.status === 404 || response.status === 405) {
          handlers.onStart?.();
          const res = await this.ask(request, options);
          const msg =
            res.answer?.main_message ||
            (res as any).main_message ||
            (typeof res.answer === "string" ? res.answer : "") ||
            "";
          if (msg) {
            handlers.onMainMessage?.(msg);
            handlers.onToken?.(msg);
          }
          if (res.safety) handlers.onSafety?.(res.safety);
          if (res.personal_evidence || res.external_sources || res.disclosure) {
            handlers.onEvidence?.({
              personal_evidence: res.personal_evidence,
              external_sources: res.external_sources,
              disclosure: res.disclosure,
            });
          }
          if (res.write_proposals) handlers.onProposals?.(res.write_proposals);
          if (res.unknowns) handlers.onUnknowns?.(res.unknowns);
          handlers.onDone?.(res);
          return;
        }

        let errPayload: unknown = undefined;
        try {
          errPayload = await response.json();
        } catch {
          errPayload = undefined;
        }

        const normalized = normalizeApiV2Error({
          response: {
            status: response.status,
            data: errPayload,
          },
        });
        handlers.onError?.(normalized);
        throw normalized;
      }

      handlers.onStart?.();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const accumulatedEnvelope: Partial<ConsumerAnswerEnvelope> = {
        answer: { main_message: "", actions: [], sections: [] },
        personal_evidence: [],
        external_sources: [],
        unknowns: [],
        write_proposals: [],
      };
      let sawTerminal = false;

      const dispatch = (event: string, rawData: string) => {
        let parsed: unknown = rawData;
        try {
          parsed = JSON.parse(rawData);
        } catch {
          parsed = rawData;
        }

        if (event === "start") {
          handlers.onStart?.();
        } else if (event === "token" || event === "message_chunk" || event === "chunk") {
          const text =
            typeof parsed === "string"
              ? parsed
              : (parsed as { text?: string; token?: string; chunk?: string })?.text ??
                (parsed as { text?: string; token?: string; chunk?: string })?.token ??
                (parsed as { text?: string; token?: string; chunk?: string })?.chunk ??
                "";
          if (text) {
            if (accumulatedEnvelope.answer) {
              accumulatedEnvelope.answer.main_message += text;
            }
            handlers.onToken?.(text);
            if (accumulatedEnvelope.answer?.main_message) {
              handlers.onMainMessage?.(accumulatedEnvelope.answer.main_message);
            }
          }
        } else if (event === "main_message") {
          const msg =
            typeof parsed === "string"
              ? parsed
              : (parsed as { main_message?: string; message?: string })?.main_message ??
                (parsed as { main_message?: string; message?: string })?.message ??
                "";
          if (accumulatedEnvelope.answer) {
            accumulatedEnvelope.answer.main_message = msg;
          }
          handlers.onMainMessage?.(msg);
        } else if (event === "safety") {
          const safety = (
            (parsed as { safety?: ConsumerSafetyGuidanceDto })?.safety ?? parsed
          ) as ConsumerSafetyGuidanceDto;
          accumulatedEnvelope.safety = safety;
          handlers.onSafety?.(safety);
        } else if (event === "evidence") {
          const ev = parsed as {
            personal_evidence?: ConsumerPersonalEvidenceDto[];
            external_sources?: ConsumerExternalSourceDto[];
            disclosure?: ConsumerDisclosureDto;
          };
          if (ev.personal_evidence) accumulatedEnvelope.personal_evidence = ev.personal_evidence;
          if (ev.external_sources) accumulatedEnvelope.external_sources = ev.external_sources;
          if (ev.disclosure) accumulatedEnvelope.disclosure = ev.disclosure;
          handlers.onEvidence?.(ev);
        } else if (event === "proposals" || event === "write_proposals") {
          const proposals = (
            Array.isArray(parsed)
              ? parsed
              : (parsed as { write_proposals?: WriteProposalDto[] })?.write_proposals ?? []
          ) as WriteProposalDto[];
          accumulatedEnvelope.write_proposals = proposals;
          handlers.onProposals?.(proposals);
        } else if (event === "unknowns") {
          const unks = (
            Array.isArray(parsed)
              ? parsed
              : (parsed as { unknowns?: ConsumerUnknownDto[] })?.unknowns ?? []
          ) as ConsumerUnknownDto[];
          accumulatedEnvelope.unknowns = unks;
          handlers.onUnknowns?.(unks);
        } else if (event === "done" || event === "complete") {
          sawTerminal = true;
          const envelope = (
            (parsed as { data?: ConsumerAnswerEnvelope })?.data ?? parsed
          ) as ConsumerAnswerEnvelope;
          const finalEnvelope: ConsumerAnswerEnvelope = {
            answer: {
              main_message:
                envelope?.answer?.main_message ||
                (envelope as any)?.main_message ||
                (typeof envelope?.answer === "string" ? envelope.answer : "") ||
                accumulatedEnvelope.answer?.main_message ||
                "",
              actions:
                envelope?.answer?.actions ||
                accumulatedEnvelope.answer?.actions ||
                [],
              sections:
                envelope?.answer?.sections ||
                accumulatedEnvelope.answer?.sections ||
                [],
            },
            personal_evidence:
              envelope?.personal_evidence ?? accumulatedEnvelope.personal_evidence,
            external_sources:
              envelope?.external_sources ?? accumulatedEnvelope.external_sources,
            unknowns: envelope?.unknowns ?? accumulatedEnvelope.unknowns,
            safety: envelope?.safety ?? accumulatedEnvelope.safety,
            write_proposals:
              envelope?.write_proposals ?? accumulatedEnvelope.write_proposals,
            disclosure: envelope?.disclosure ?? accumulatedEnvelope.disclosure,
            conversation_id:
              envelope?.conversation_id ?? accumulatedEnvelope.conversation_id,
            created_at: envelope?.created_at ?? accumulatedEnvelope.created_at,
          };
          handlers.onDone?.(finalEnvelope);
        } else if (event === "error") {
          sawTerminal = true;
          const errObj = normalizeApiV2Error(parsed);
          handlers.onError?.(errObj);
        }
      };

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let sepIndex = buffer.indexOf("\n\n");
          while (sepIndex !== -1) {
            const block = buffer.slice(0, sepIndex);
            buffer = buffer.slice(sepIndex + 2);
            const frame = parseSseFrame(block);
            if (frame) dispatch(frame.event, frame.data);
            sepIndex = buffer.indexOf("\n\n");
          }
        }
        const tail = parseSseFrame(buffer);
        if (tail) dispatch(tail.event, tail.data);
      } finally {
        reader.releaseLock();
      }

      if (!sawTerminal) {
        const finalEnvelope: ConsumerAnswerEnvelope = {
          answer: {
            main_message: accumulatedEnvelope.answer?.main_message || "",
            actions: accumulatedEnvelope.answer?.actions || [],
            sections: accumulatedEnvelope.answer?.sections || [],
          },
          personal_evidence: accumulatedEnvelope.personal_evidence,
          external_sources: accumulatedEnvelope.external_sources,
          unknowns: accumulatedEnvelope.unknowns,
          safety: accumulatedEnvelope.safety,
          write_proposals: accumulatedEnvelope.write_proposals,
          disclosure: accumulatedEnvelope.disclosure,
        };
        handlers.onDone?.(finalEnvelope);
      }
    } catch (streamErr) {
      const normalized = normalizeApiV2Error(streamErr);
      handlers.onError?.(normalized);
      throw normalized;
    }
  }
  async createCaptureSession(
    request: CreateCaptureSessionRequest,
    options?: ApiV2RequestOptions,
  ): Promise<CaptureSessionV2> {
    const res = await this.post<CaptureSessionV2>("/capture/sessions", request, options);
    return res.data;
  }

  async uploadCaptureArtifact(
    sessionId: string,
    file: File | Blob,
    options?: ApiV2RequestOptions & { onProgress?: (progress: number) => void },
  ): Promise<CaptureArtifactV2> {
    const formData = new FormData();
    formData.append("file", file);
    const headers = {
      ...(options?.headers ?? {}),
    };
    const res = await this.request<CaptureArtifactV2>({
      ...options,
      url: `/capture/sessions/${encodeURIComponent(sessionId)}/artifacts`,
      method: "POST",
      data: formData,
      headers,
    });
    return res.data;
  }

  async getCaptureSession(
    sessionId: string,
    options?: ApiV2RequestOptions,
  ): Promise<CaptureSessionV2> {
    const res = await this.get<CaptureSessionV2>(
      `/capture/sessions/${encodeURIComponent(sessionId)}`,
      options,
    );
    return res.data;
  }

  async reviewCaptureCandidate(
    candidateId: string,
    action: "accept" | "confirm" | "reject" | "edit",
    payload?: Partial<ReviewCaptureCandidateRequest>,
    options?: ApiV2RequestOptions,
  ): Promise<CaptureCandidateV2> {
    const res = await this.post<CaptureCandidateV2>(
      `/capture/candidates/${encodeURIComponent(candidateId)}/review`,
      { action, ...(payload ?? {}) },
      options,
    );
    return res.data;
  }

  async commitCaptureSession(
    sessionId: string,
    payload?: CommitCaptureSessionRequest,
    options?: ApiV2RequestOptions,
  ): Promise<CommitCaptureSessionResponse> {
    const res = await this.post<CommitCaptureSessionResponse>(
      `/capture/sessions/${encodeURIComponent(sessionId)}/commit`,
      payload ?? {},
      options,
    );
    return res.data;
  }

  async getCareSummary(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<CareSummaryDto> {
    const res = await this.get<CareSummaryDto>("/care/summary", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async getVisits(
    params?: { status?: string; limit?: number },
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<CareVisitDto[]> {
    const res = await this.get<CareVisitDto[] | { items: CareVisitDto[] }>("/care/visits", {
      ...options,
      params: { ...(options?.params ?? {}), ...(params ?? {}) },
      profileId: profileId ?? options?.profileId,
    });
    if (Array.isArray(res.data)) return res.data;
    if (
      res.data &&
      typeof res.data === "object" &&
      "items" in res.data &&
      Array.isArray((res.data as { items: CareVisitDto[] }).items)
    ) {
      return (res.data as { items: CareVisitDto[] }).items;
    }
    return [];
  }

  async createVisit(
    data: Partial<CareVisitDto> & { title: string; scheduled_at: string },
    options?: ApiV2RequestOptions,
  ): Promise<CareVisitDto> {
    const res = await this.post<CareVisitDto>("/care/visits", data, options);
    return res.data;
  }

  async prepareVisit(
    visitId: string,
    data: VisitPrepRequestDto,
    options?: ApiV2RequestOptions,
  ): Promise<VisitPrepHandoffSummaryDto> {
    const res = await this.post<VisitPrepHandoffSummaryDto>(
      `/care/visits/${encodeURIComponent(visitId)}/prepare`,
      data,
      options,
    );
    return res.data;
  }

  async checkSymptoms(
    data: SymptomCheckRequestDto,
    options?: ApiV2RequestOptions,
  ): Promise<SymptomCheckResultDto> {
    const res = await this.post<SymptomCheckResultDto>("/care/check-symptoms", data, options);
    return res.data;
  }

  async getMedicationsHub(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<MedicationsHubDto> {
    const res = await this.get<MedicationsHubDto>("/health/medications/hub", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async checkMedicationSafety(
    data: MedicationSafetyCheckRequestDto,
    options?: ApiV2RequestOptions,
  ): Promise<MedicationSafetyCheckResultDto> {
    const res = await this.post<MedicationSafetyCheckResultDto>(
      "/health/medications/safety-check",
      data,
      options,
    );
    return res.data;
  }

  async getYouOverview(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<YouOverviewDto> {
    const res = await this.get<YouOverviewDto>("/you/overview", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async getProfileDetails(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<ProfileDetailsDto> {
    const res = await this.get<ProfileDetailsDto>("/you/profile", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateProfileDetails(
    data: Partial<ProfileDetailsDto>,
    options?: ApiV2RequestOptions,
  ): Promise<ProfileDetailsDto> {
    const res = await this.patch<ProfileDetailsDto>("/you/profile", data, options);
    return res.data;
  }

  async getEmergencyCard(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<EmergencyCardDto> {
    const res = await this.get<EmergencyCardDto>("/you/emergency-card", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateEmergencyCard(
    data: Partial<EmergencyCardDto>,
    options?: ApiV2RequestOptions,
  ): Promise<EmergencyCardDto> {
    const res = await this.put<EmergencyCardDto>("/you/emergency-card", data, options);
    return res.data;
  }

  async getSharingOverview(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<SharingOverviewDto> {
    const res = await this.get<SharingOverviewDto>("/you/sharing", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async createSharingGrant(
    data: SharingGrantRequestDto,
    options?: ApiV2RequestOptions,
  ): Promise<SharingGrantDto> {
    const res = await this.post<SharingGrantDto>("/you/sharing/grants", data, options);
    return res.data;
  }

  async revokeSharingGrant(
    grantId: string,
    options?: ApiV2RequestOptions,
  ): Promise<{ success: boolean; revoked_at: string }> {
    const res = await this.post<{ success: boolean; revoked_at: string }>(
      `/you/sharing/grants/${encodeURIComponent(grantId)}/revoke`,
      {},
      options,
    );
    return res.data;
  }

  async getSharingAccessLogs(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<SharingAccessLogDto[]> {
    const res = await this.get<SharingAccessLogDto[] | { items: SharingAccessLogDto[] }>(
      "/you/sharing/logs",
      {
        ...options,
        profileId: profileId ?? options?.profileId,
      },
    );
    if (Array.isArray(res.data)) return res.data;
    if (
      res.data &&
      typeof res.data === "object" &&
      "items" in res.data &&
      Array.isArray((res.data as { items: SharingAccessLogDto[] }).items)
    ) {
      return (res.data as { items: SharingAccessLogDto[] }).items;
    }
    return [];
  }

  async getAiTransparency(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<AiTransparencyDto> {
    const res = await this.get<AiTransparencyDto>("/you/privacy/ai-transparency", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateAiPreferences(
    data: Partial<AiPreferencesDto>,
    options?: ApiV2RequestOptions,
  ): Promise<AiPreferencesDto> {
    const res = await this.patch<AiPreferencesDto>(
      "/you/privacy/ai-preferences",
      data,
      options,
    );
    return res.data;
  }

  async getIntegrations(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<ConnectedHealthSourcesDto> {
    const res = await this.get<ConnectedHealthSourcesDto>("/you/integrations", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateIntegrationSource(
    sourceId: string,
    data: Partial<ConnectedHealthSourceDto>,
    options?: ApiV2RequestOptions,
  ): Promise<ConnectedHealthSourceDto> {
    const res = await this.patch<ConnectedHealthSourceDto>(
      `/you/integrations/sources/${encodeURIComponent(sourceId)}`,
      data,
      options,
    );
    return res.data;
  }

  async syncIntegrationSource(
    sourceId: string,
    options?: ApiV2RequestOptions,
  ): Promise<{ success: boolean; synced_at: string }> {
    const res = await this.post<{ success: boolean; synced_at: string }>(
      `/you/integrations/sources/${encodeURIComponent(sourceId)}/sync`,
      {},
      options,
    );
    return res.data;
  }

  async getNotificationPreferences(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<NotificationPreferencesDto> {
    const res = await this.get<NotificationPreferencesDto>("/you/notifications", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateNotificationPreferences(
    data: Partial<NotificationPreferencesDto>,
    options?: ApiV2RequestOptions,
  ): Promise<NotificationPreferencesDto> {
    const res = await this.patch<NotificationPreferencesDto>(
      "/you/notifications",
      data,
      options,
    );
    return res.data;
  }

  async getSecuritySettings(
    profileId?: string | null,
    options?: ApiV2RequestOptions,
  ): Promise<SecuritySettingsDto> {
    const res = await this.get<SecuritySettingsDto>("/you/settings/security", {
      ...options,
      profileId: profileId ?? options?.profileId,
    });
    return res.data;
  }

  async updateSecuritySettings(
    data: Partial<SecuritySettingsDto>,
    options?: ApiV2RequestOptions,
  ): Promise<SecuritySettingsDto> {
    const res = await this.patch<SecuritySettingsDto>(
      "/you/settings/security",
      data,
      options,
    );
    return res.data;
  }

  async revokeSession(
    sessionId: string,
    options?: ApiV2RequestOptions,
  ): Promise<{ success: boolean; revoked_id: string }> {
    const res = await this.delete<{ success: boolean; revoked_id: string }>(
      `/you/settings/sessions/${encodeURIComponent(sessionId)}`,
      options,
    );
    return res.data;
  }

  async revokeAllOtherSessions(
    options?: ApiV2RequestOptions,
  ): Promise<{ success: boolean; revoked_count: number }> {
    const res = await this.post<{ success: boolean; revoked_count: number }>(
      "/you/settings/sessions/revoke-others",
      {},
      options,
    );
    return res.data;
  }
}

export const v2Client = new ApiV2Client();

export const apiV2Get = <T>(url: string, options?: ApiV2RequestOptions) =>
  v2Client.get<T>(url, options);

export const apiV2Post = <T>(url: string, data?: unknown, options?: ApiV2RequestOptions) =>
  v2Client.post<T>(url, data, options);

export const apiV2Put = <T>(url: string, data?: unknown, options?: ApiV2RequestOptions) =>
  v2Client.put<T>(url, data, options);

export const apiV2Patch = <T>(url: string, data?: unknown, options?: ApiV2RequestOptions) =>
  v2Client.patch<T>(url, data, options);

export const apiV2Delete = <T>(url: string, options?: ApiV2RequestOptions) =>
  v2Client.delete<T>(url, options);

export const apiV2Request = <T>(config: ApiV2RequestConfig) =>
  v2Client.request<T>(config);

export const apiV2FetchData = <T>(url: string, options?: ApiV2RequestOptions) =>
  v2Client.fetchData<T>(url, options);

export const apiV2GetHealthSummary = (profileId?: string | null, options?: ApiV2RequestOptions) =>
  v2Client.getHealthSummary(profileId, options);

export const apiV2GetHealthTimeline = (
  params?: HealthTimelineParams,
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getHealthTimeline(params, profileId, options);

export const apiV2UpdateDemographics = (
  data: Partial<HealthDemographicsDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateDemographics(data, options);

export const apiV2AddAllergy = (
  data: Omit<HealthAllergyDto, "id">,
  options?: ApiV2RequestOptions,
) => v2Client.addAllergy(data, options);

export const apiV2UpdateAllergy = (
  id: string,
  data: Partial<HealthAllergyDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateAllergy(id, data, options);

export const apiV2DeleteAllergy = (id: string, options?: ApiV2RequestOptions) =>
  v2Client.deleteAllergy(id, options);

export const apiV2AddCondition = (
  data: Omit<HealthConditionDto, "id">,
  options?: ApiV2RequestOptions,
) => v2Client.addCondition(data, options);

export const apiV2UpdateCondition = (
  id: string,
  data: Partial<HealthConditionDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateCondition(id, data, options);

export const apiV2DeleteCondition = (id: string, options?: ApiV2RequestOptions) =>
  v2Client.deleteCondition(id, options);

export const apiV2AddMeasurement = (
  data: Omit<HealthMeasurementDto, "id">,
  options?: ApiV2RequestOptions,
) => v2Client.addMeasurement(data, options);

export const apiV2Ask = (
  request: ConsumerAskRequest,
  options?: ApiV2RequestOptions,
) => v2Client.ask(request, options);

export const apiV2StreamAsk = (
  request: ConsumerAskRequest,
  handlers: ConsumerAskStreamHandlers,
  options?: ApiV2RequestOptions,
) => v2Client.streamAsk(request, handlers, options);

export const apiV2CreateCaptureSession = (
  request: CreateCaptureSessionRequest,
  options?: ApiV2RequestOptions,
) => v2Client.createCaptureSession(request, options);

export const apiV2UploadCaptureArtifact = (
  sessionId: string,
  file: File | Blob,
  options?: ApiV2RequestOptions & { onProgress?: (progress: number) => void },
) => v2Client.uploadCaptureArtifact(sessionId, file, options);

export const apiV2GetCaptureSession = (
  sessionId: string,
  options?: ApiV2RequestOptions,
) => v2Client.getCaptureSession(sessionId, options);

export const apiV2ReviewCaptureCandidate = (
  candidateId: string,
  action: "accept" | "confirm" | "reject" | "edit",
  payload?: Partial<ReviewCaptureCandidateRequest>,
  options?: ApiV2RequestOptions,
) => v2Client.reviewCaptureCandidate(candidateId, action, payload, options);

export const apiV2CommitCaptureSession = (
  sessionId: string,
  payload?: CommitCaptureSessionRequest,
  options?: ApiV2RequestOptions,
) => v2Client.commitCaptureSession(sessionId, payload, options);

export const apiV2GetCareSummary = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getCareSummary(profileId, options);

export const apiV2GetVisits = (
  params?: { status?: string; limit?: number },
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getVisits(params, profileId, options);

export const apiV2CreateVisit = (
  data: Partial<CareVisitDto> & { title: string; scheduled_at: string },
  options?: ApiV2RequestOptions,
) => v2Client.createVisit(data, options);

export const apiV2PrepareVisit = (
  visitId: string,
  data: VisitPrepRequestDto,
  options?: ApiV2RequestOptions,
) => v2Client.prepareVisit(visitId, data, options);

export const apiV2CheckSymptoms = (
  data: SymptomCheckRequestDto,
  options?: ApiV2RequestOptions,
) => v2Client.checkSymptoms(data, options);

export const apiV2GetMedicationsHub = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getMedicationsHub(profileId, options);

export const apiV2CheckMedicationSafety = (
  data: MedicationSafetyCheckRequestDto,
  options?: ApiV2RequestOptions,
) => v2Client.checkMedicationSafety(data, options);

export const apiV2GetYouOverview = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getYouOverview(profileId, options);

export const apiV2GetProfileDetails = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getProfileDetails(profileId, options);

export const apiV2UpdateProfileDetails = (
  data: Partial<ProfileDetailsDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateProfileDetails(data, options);

export const apiV2GetEmergencyCard = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getEmergencyCard(profileId, options);

export const apiV2UpdateEmergencyCard = (
  data: Partial<EmergencyCardDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateEmergencyCard(data, options);

export const apiV2GetSharingOverview = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getSharingOverview(profileId, options);

export const apiV2CreateSharingGrant = (
  data: SharingGrantRequestDto,
  options?: ApiV2RequestOptions,
) => v2Client.createSharingGrant(data, options);

export const apiV2RevokeSharingGrant = (
  grantId: string,
  options?: ApiV2RequestOptions,
) => v2Client.revokeSharingGrant(grantId, options);

export const apiV2GetSharingAccessLogs = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getSharingAccessLogs(profileId, options);

export const apiV2GetAiTransparency = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getAiTransparency(profileId, options);

export const apiV2UpdateAiPreferences = (
  data: Partial<AiPreferencesDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateAiPreferences(data, options);

export const apiV2GetIntegrations = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getIntegrations(profileId, options);

export const apiV2UpdateIntegrationSource = (
  sourceId: string,
  data: Partial<ConnectedHealthSourceDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateIntegrationSource(sourceId, data, options);

export const apiV2SyncIntegrationSource = (
  sourceId: string,
  options?: ApiV2RequestOptions,
) => v2Client.syncIntegrationSource(sourceId, options);

export const apiV2GetNotificationPreferences = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getNotificationPreferences(profileId, options);

export const apiV2UpdateNotificationPreferences = (
  data: Partial<NotificationPreferencesDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateNotificationPreferences(data, options);

export const apiV2GetSecuritySettings = (
  profileId?: string | null,
  options?: ApiV2RequestOptions,
) => v2Client.getSecuritySettings(profileId, options);

export const apiV2UpdateSecuritySettings = (
  data: Partial<SecuritySettingsDto>,
  options?: ApiV2RequestOptions,
) => v2Client.updateSecuritySettings(data, options);

export const apiV2RevokeSession = (
  sessionId: string,
  options?: ApiV2RequestOptions,
) => v2Client.revokeSession(sessionId, options);

export const apiV2RevokeAllOtherSessions = (
  options?: ApiV2RequestOptions,
) => v2Client.revokeAllOtherSessions(options);
