import apiClient from './client';
import type { CourseTreeNode, CourseStructureResponse } from '@/types';

/**
 * Синхронизация структуры курса из внешнего источника.
 */
export const syncCourse = async (payload: CourseStructureResponse): Promise<any> => {
  const { data } = await apiClient.post('/courses/sync', payload);
  return data;
};

/**
 * Получение иерархии курса в виде дерева.
 */
export const getCourseTree = async (courseId: string): Promise<CourseTreeNode[]> => {
  const { data } = await apiClient.get<CourseTreeNode[]>(`/courses/${courseId}/tree`);
  return data;
};

/**
 * Перезаписать список компетенций, которые элемент выдаёт при прохождении
 * (SWRL H-2). Возвращает обновлённый assesses.
 */
export const setElementCompetencies = async (
  elementId: string,
  competencyIds: string[],
): Promise<{ element_id: string; assesses: Array<{ id: string; name: string }> }> => {
  const { data } = await apiClient.put(`/elements/${elementId}/competencies`, {
    competency_ids: competencyIds,
  });
  return data;
};

/**
 * Переключить флаг обязательности элемента (влияет на Roll-up:
 * модуль завершён только если все mandatory потомки завершены).
 */
export const setElementMandatory = async (
  elementId: string,
  isMandatory: boolean,
): Promise<{ element_id: string; is_mandatory: boolean }> => {
  const { data } = await apiClient.put(`/elements/${elementId}/mandatory`, {
    is_mandatory: isMandatory,
  });
  return data;
};
