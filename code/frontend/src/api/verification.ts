import apiClient from './client';
import type { BlockingExplanation, VerificationReport } from '@/types';

/**
 * Базовая верификация курса по СВ-1/2/3.
 * При full=true дополнительно считаются СВ-4 Redundancy и СВ-5 Subsumption
 */
export const getVerificationReport = async (
  courseId: string,
  full = false,
): Promise<VerificationReport> => {
  const { data } = await apiClient.get<VerificationReport>(
    `/verify/course/${courseId}`,
    { params: { full } },
  );
  return data;
};

/**
 * Объяснение (не)доступа к элементу: applicable_policies + cascade_blocker
 */
export const getBlockingExplanation = async (
  studentId: string,
  elementId: string,
): Promise<BlockingExplanation> => {
  const { data } = await apiClient.get<BlockingExplanation>(
    `/access/student/${studentId}/element/${elementId}/explain`,
  );
  return data;
};
