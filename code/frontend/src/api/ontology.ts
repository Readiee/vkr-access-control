import apiClient from './client';
import type { OntologyMeta, ProgressEvent, AvailableElementsResponse } from '@/types';

/**
 * Метаданные онтологии: типы правил, статусы, элементы, компетенции
 */
export const getMeta = async (): Promise<OntologyMeta> => {
  const { data } = await apiClient.get<OntologyMeta>('/ontology/meta');
  return data;
};

/**
 * Отправка события прогресса
 */
export const registerProgress = async (event: ProgressEvent): Promise<any> => {
  const { data } = await apiClient.post('/events/progress', event);
  return data;
};

/**
 * Текущие доступы студента в рамках курса
 */
export const getStudentAccess = async (studentId: string, courseId: string): Promise<AvailableElementsResponse> => {
  const { data } = await apiClient.get<AvailableElementsResponse>(`/access/student/${studentId}/course/${courseId}`);
  return data;
};
