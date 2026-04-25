import apiClient from './client';
import type { PolicyCreate, PolicyResponse } from '@/types';

/**
 * Список всех политик доступа с опциональной фильтрацией
 */
export const getPolicies = async (courseId?: string, elementId?: string): Promise<PolicyResponse[]> => {
  const { data } = await apiClient.get<PolicyResponse[]>('/policies', {
    params: {
      course_id: courseId,
      element_id: elementId
    }
  });
  return data;
};

/**
 * Создать новую политику доступа
 */
export const createPolicy = async (policy: PolicyCreate): Promise<PolicyResponse> => {
  const { data } = await apiClient.post<PolicyResponse>('/policies', policy);
  return data;
};

/**
 * Обновить существующую политику доступа
 */
export const updatePolicy = async (policyId: string, data: Partial<PolicyCreate>): Promise<PolicyResponse> => {
  const response = await apiClient.put<PolicyResponse>(`/policies/${policyId}`, data);
  return response.data;
};

/**
 * Удалить политику доступа из онтологии
 */
export const deletePolicy = async (policyId: string): Promise<void> => {
  await apiClient.delete(`/policies/${policyId}`);
};
