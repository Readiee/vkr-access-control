export enum RuleType {
  VIEWED_REQUIRED = 'viewed_required',
  COMPLETION_REQUIRED = 'completion_required',
  GRADE_REQUIRED = 'grade_required',
  COMPETENCY_REQUIRED = 'competency_required',
  DATE_RESTRICTED = 'date_restricted',
  AND_COMBINATION = 'and_combination',
  OR_COMBINATION = 'or_combination',
  GROUP_RESTRICTED = 'group_restricted',
  AGGREGATE_REQUIRED = 'aggregate_required',
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

export enum AggregateFunction {
  AVG = 'AVG',
  SUM = 'SUM',
  COUNT = 'COUNT',
}

export enum VerificationPropertyStatus {
  PASSED = 'passed',
  FAILED = 'failed',
  UNKNOWN = 'unknown',
}
