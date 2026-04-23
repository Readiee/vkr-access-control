import apiClient from './client';
import type {
  SandboxActionResult,
  SandboxProgressPayload,
  SandboxState,
} from '@/types';

export const getSandboxState = async (courseId: string): Promise<SandboxState> => {
  const { data } = await apiClient.get<SandboxState>('/sandbox/state', {
    params: { course_id: courseId },
  });
  return data;
};

export const simulateSandboxProgress = async (
  payload: SandboxProgressPayload,
): Promise<SandboxActionResult> => {
  const { data } = await apiClient.post<SandboxActionResult>('/sandbox/progress', payload);
  return data;
};

export const rollbackSandboxProgress = async (
  elementId: string,
): Promise<SandboxActionResult> => {
  const { data } = await apiClient.delete<SandboxActionResult>(`/sandbox/progress/${elementId}`);
  return data;
};

export const resetSandbox = async (): Promise<SandboxActionResult> => {
  const { data } = await apiClient.post<SandboxActionResult>('/sandbox/reset');
  return data;
};

export const setSandboxCompetencies = async (
  competencyIds: string[],
): Promise<SandboxActionResult> => {
  const { data } = await apiClient.put<SandboxActionResult>('/sandbox/competencies', competencyIds);
  return data;
};

export const setSandboxGroup = async (
  groupId: string | null,
): Promise<SandboxActionResult> => {
  const { data } = await apiClient.put<SandboxActionResult>('/sandbox/group', { group_id: groupId });
  return data;
};
