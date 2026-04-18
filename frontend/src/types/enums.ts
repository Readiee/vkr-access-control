export enum RuleType {
  VIEWED_REQUIRED = 'viewed_required',
  COMPLETION_REQUIRED = 'completion_required',
  GRADE_REQUIRED = 'grade_required',
  COMPETENCY_REQUIRED = 'competency_required',
  DATE_RESTRICTED = 'date_restricted',
}

export enum ElementType {
  COURSE = 'course',
  MODULE = 'module',
  LECTURE = 'lecture',
  TEST = 'test',
  PRACTICE = 'practice',
  ASSIGNMENT = 'assignment',
}

export enum ProgressStatus {
  VIEWED = 'viewed',
  COMPLETED = 'completed',
  PASSED = 'passed',
  FAILED = 'failed',
}
