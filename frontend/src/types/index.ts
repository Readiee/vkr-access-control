import { RuleType, ElementType, ProgressStatus } from './enums';

export { RuleType, ElementType, ProgressStatus };

export type EventType = 'viewed' | 'completed' | 'graded' | 'failed';

export interface Competency {
  id: string;
  name: string;
}

export interface OntologyMeta {
  rule_types: RuleType[];
  statuses: string[];
  competencies: Competency[];
  course_elements?: CourseElement[]; // Добавлено для согласованности с хранилищем (МБ это можно удалить)
}

export interface PolicyBase {
  source_element_id: string;
  rule_type: RuleType;
  target_element_id?: string | null;
  target_competency_id?: string | null;
  passing_threshold?: number | null;
  available_from?: string | null; // ISO Date string
  available_until?: string | null; // ISO Date string
  author_id: string;
}

export interface PolicyCreate extends PolicyBase {
  is_active?: boolean;
}

export interface Policy extends PolicyBase {
  id: string;
  is_active: boolean;
}

export interface PolicyResponse extends Policy {}

export interface CourseElement {
  id: string;
  name: string;
  type: string;
  is_required?: boolean;
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

export interface CourseTreeNode {
  key: string;
  label?: string;
  data: CourseElement & { policies?: PolicyResponse[] };
  children?: CourseTreeNode[];
}
