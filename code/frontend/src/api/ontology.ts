import apiClient from './client';
import type { OntologyMeta, ProgressEvent, AvailableElementsResponse } from '@/types';

/**
 * Получение метаданных (типы правил, статусы, элементы, компетенции) для UI.
 */
export const getMeta = async (): Promise<OntologyMeta> => {
  const { data } = await apiClient.get<OntologyMeta>('/ontology/meta');
  return data;
};

/**
 * Эмуляция события прогресса.
 */
export const registerProgress = async (event: ProgressEvent): Promise<any> => {
  const { data } = await apiClient.post('/events/progress', event);
  return data;
};

/**
 * Получение текущих доступов студента.
 */
export const getStudentAccess = async (studentId: string, courseId: string): Promise<AvailableElementsResponse> => {
  const { data } = await apiClient.get<AvailableElementsResponse>(`/access/student/${studentId}/course/${courseId}`);
  return data;
};
