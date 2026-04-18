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
