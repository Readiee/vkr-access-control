import apiClient from './client';
import type {
  SandboxActionResult,
  SandboxProgressPayload,
  SandboxState,
  SandboxStudent,
} from '@/types';

export const listSandboxStudents = async (): Promise<SandboxStudent[]> => {
  const { data } = await apiClient.get<SandboxStudent[]>('/sandbox/students');
  return data;
};

export const getSandboxState = async (
  courseId: string,
  studentId?: string | null,
): Promise<SandboxState> => {
  const params: Record<string, string> = { course_id: courseId };
  if (studentId) params.student_id = studentId;
  const { data } = await apiClient.get<SandboxState>('/sandbox/state', { params });
  return data;
};

export const simulateSandboxProgress = async (
  payload: SandboxProgressPayload,
  studentId?: string | null,
): Promise<SandboxActionResult> => {
  const params = studentId ? { student_id: studentId } : undefined;
  const { data } = await apiClient.post<SandboxActionResult>('/sandbox/progress', payload, { params });
  return data;
};

export const rollbackSandboxProgress = async (
  elementId: string,
  studentId?: string | null,
): Promise<SandboxActionResult> => {
  const params = studentId ? { student_id: studentId } : undefined;
  const { data } = await apiClient.delete<SandboxActionResult>(`/sandbox/progress/${elementId}`, { params });
  return data;
};

export const resetSandbox = async (studentId?: string | null): Promise<SandboxActionResult> => {
  const params = studentId ? { student_id: studentId } : undefined;
  const { data } = await apiClient.post<SandboxActionResult>('/sandbox/reset', null, { params });
  return data;
};

export const setSandboxCompetencies = async (
  competencyIds: string[],
  studentId?: string | null,
): Promise<SandboxActionResult> => {
  const params = studentId ? { student_id: studentId } : undefined;
  const { data } = await apiClient.put<SandboxActionResult>('/sandbox/competencies', competencyIds, { params });
  return data;
};
