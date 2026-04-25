export * from './enums';
import { RuleType, ProgressStatus, AggregateFunction, VerificationPropertyStatus } from './enums';

export type EventType = 'viewed' | 'completed' | 'graded' | 'failed';

export interface Competency {
  id: string;
  name: string;
  parent_id?: string | null;
}

export interface Group {
  id: string;
  name: string;
}

export interface OntologyMeta {
  rule_types: RuleType[];
  statuses: string[];
  competencies: Competency[];
  course_elements?: CourseElement[];
  groups?: Group[];
}

export interface PolicyBase {
  source_element_id?: string | null;
  rule_type: RuleType;
  target_element_id?: string | null;
  target_competency_id?: string | null;
  passing_threshold?: number | null;
  valid_from?: string | null;
  valid_until?: string | null;
  restricted_to_group_id?: string | null;
  subpolicy_ids?: string[] | null;
  aggregate_function?: AggregateFunction | null;
  aggregate_element_ids?: string[] | null;
  author_id: string;
}

export interface PolicyCreate extends PolicyBase {
  is_active?: boolean;
}

export interface Policy extends PolicyBase {
  id: string;
  name?: string;
  is_active: boolean;
  target_element_name?: string | null;
  competency_name?: string | null;
  restricted_to_group_name?: string | null;
  aggregate_element_names?: string[];
  subpolicies_detail?: Policy[];
}

export type PolicyResponse = Policy;

export interface CourseElement {
  id: string;
  name: string;
  type: string;
  is_mandatory?: boolean;
  assesses?: Array<{ id: string; name: string }>;
}

export interface CourseStructureResponse {
  course_id: string;
  elements: CourseElement[];
}

export interface ProgressEvent {
  student_id: string;
  element_id: string;
  event_type: EventType;
  grade?: number | null;
  timestamp?: string | null;
}

export interface AvailableElementsResponse {
  available_elements: string[];
}

// ---- Sandbox ----

export interface SandboxProgressPayload {
  element_id: string;
  status: ProgressStatus;
  grade?: number | null;
}

export interface SandboxCompetencyPayload {
  competency_id: string;
  has_competency: boolean;
}

export interface SandboxProgressEntry {
  status: string;
  grade?: number | null;
}

export interface SandboxState {
  student_id: string;
  student_name: string;
  available_elements: string[];
  progress: Record<string, SandboxProgressEntry>;
  active_competencies: string[];
  group_id?: string | null;
  group_name?: string | null;
}

export interface SandboxActionResult {
  status: string;
  message: string;
}

export interface CourseTreeNode {
  key: string;
  label?: string;
  data: CourseElement & { policies?: PolicyResponse[] };
  children?: CourseTreeNode[];
}

// Верификация курса по СВ-1…СВ-5

export interface PropertyViolation {
  code: string;
  message?: string;
  // acyclicity
  path?: string[];
  path_names?: string[];
  policies?: string[];
  policy_names?: string[];
  // reachability / subsumption-elem shared
  element_id?: string;
  element_name?: string;
  policy_id?: string;
  policy_name?: string;
  rule_type?: string;
  reason?: string;
  // subsumption/redundancy
  dominant?: string;
  dominant_name?: string;
  dominated?: string;
  dominated_name?: string;
  element?: string;
  witness?: string;
}

export interface PropertyReport {
  status: VerificationPropertyStatus | string;
  violations?: PropertyViolation[];
}

export interface VerificationReport {
  course_id: string;
  run_id: string;
  timestamp: string;
  duration_ms: number;
  partial: boolean;
  properties: Record<string, PropertyReport>;
  summary?: string;
}

// Объяснение блокировки доступа

export interface SubpolicyDiagnosis {
  id: string;
  name: string;
  rule_type: string;
  satisfied: boolean;
  failure_reason?: string | null;
}

export interface ApplicablePolicyTrace {
  policy_id: string;
  policy_name?: string | null;
  rule_type: string;
  satisfied: boolean;
  failure_reason?: string | null;
  witness?: Record<string, any> & { subpolicies?: SubpolicyDiagnosis[] };
}

export interface JustificationBodyFact {
  predicate: string;
  subject?: string | null;
  object?: unknown;
}

export interface JustificationNode {
  status: 'satisfied' | 'unsatisfied' | 'available' | 'unavailable';
  rule_template: string;
  policy_id?: string | null;
  variable_bindings?: Record<string, unknown>;
  body_facts?: JustificationBodyFact[];
  note?: string | null;
  children?: JustificationNode[];
}

export interface BlockingExplanation {
  element_id: string;
  element_name?: string | null;
  student_id: string;
  student_name?: string | null;
  is_available: boolean;
  cascade_blocker?: string | null;
  cascade_blocker_name?: string | null;
  cascade_reason?: string | null;
  applicable_policies: ApplicablePolicyTrace[];
  justification?: JustificationNode | null;
}
