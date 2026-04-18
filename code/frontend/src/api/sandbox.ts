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

export const SandboxAPI = {
  /**
   * Получить состояние песочницы (доступы и прогресс)
   */
  getState: async (courseId: string) => {
    const { data } = await apiClient.get('/sandbox/state', { params: { course_id: courseId } });
    return data;
  },

  /**
   * Эмулирует прохождение учебного элемента в песочнице.
   */
  simulateProgress: async (payload: SandboxProgressPayload) => {
    const { data } = await apiClient.post('/sandbox/progress', payload);
    return data;
  },

  /**
   * Удаляет запись о прогрессе конкретного элемента и каскадно чистит родителей.
   */
  rollbackProgress: async (elementId: string) => {
    const { data } = await apiClient.delete(`/sandbox/progress/${elementId}`);
    return data;
  },

  /**
   * Полная очистка песочницы (удаление всех рекордов и компетенций).
   */
  resetAll: async () => {
    const { data } = await apiClient.post('/sandbox/reset');
    return data;
  },

  /**
   * Перезаписывает список компетенций студента.
   */
  setCompetencies: async (competencyIds: string[]) => {
    const { data } = await apiClient.put('/sandbox/competencies', competencyIds);
    return data;
  }
};
