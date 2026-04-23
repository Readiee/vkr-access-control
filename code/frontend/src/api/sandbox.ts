import apiClient from './client';
import type { ProgressStatus } from '@/types/enums';

// TODO: эти интерфейсы должны быть здесь или в types.ts

export interface SandboxProgressPayload {
  element_id: string;
  status: ProgressStatus | 'viewed';
  grade?: number | null;
}

export interface SandboxCompetencyPayload {
  competency_id: string;
  has_competency: boolean;
}

// TODO: добавить явные типы для возвращаемых данных

export interface SandboxStudent {
  id: string;
  name: string;
}

export const SandboxAPI = {
  listStudents: async (): Promise<SandboxStudent[]> => {
    const { data } = await apiClient.get('/sandbox/students');
    return data;
  },

  getState: async (courseId: string, studentId?: string | null) => {
    const params: Record<string, string> = { course_id: courseId };
    if (studentId) params.student_id = studentId;
    const { data } = await apiClient.get('/sandbox/state', { params });
    return data;
  },

  simulateProgress: async (payload: SandboxProgressPayload, studentId?: string | null) => {
    const params = studentId ? { student_id: studentId } : undefined;
    const { data } = await apiClient.post('/sandbox/progress', payload, { params });
    return data;
  },

  rollbackProgress: async (elementId: string, studentId?: string | null) => {
    const params = studentId ? { student_id: studentId } : undefined;
    const { data } = await apiClient.delete(`/sandbox/progress/${elementId}`, { params });
    return data;
  },

  resetAll: async (studentId?: string | null) => {
    const params = studentId ? { student_id: studentId } : undefined;
    const { data } = await apiClient.post('/sandbox/reset', null, { params });
    return data;
  },

  setCompetencies: async (competencyIds: string[], studentId?: string | null) => {
    const params = studentId ? { student_id: studentId } : undefined;
    const { data } = await apiClient.put('/sandbox/competencies', competencyIds, { params });
    return data;
  },
};
