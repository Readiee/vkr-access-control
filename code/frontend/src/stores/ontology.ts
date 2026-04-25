import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { getMeta, getCourseTree } from '@/api';
import type {
  Competency,
  CourseElement,
  CourseTreeNode,
  Group,
  PolicyResponse,
  VerificationReport,
} from '@/types';

interface StoredVerification {
  courseId: string;
  report: VerificationReport;
  savedAt: number;
  policiesVersionAtSave: number;
}

export const useOntologyStore = defineStore('ontology', () => {
  const ruleTypes = ref<string[]>([]);
  const statuses = ref<string[]>([]);
  const competencies = ref<Competency[]>([]);
  const groups = ref<Group[]>([]);
  const courses = ref<CourseElement[]>([]);
  const currentCourseTree = ref<CourseTreeNode[]>([]);
  const currentCourseId = ref<string | null>(null);
  
  const isLoading = ref<boolean>(false);
  const error = ref<string | null>(null);
  const isLoaded = ref<boolean>(false);

  // Счётчик изменений политик — bump при каждом CRUD. Отчёт верификации
  // хранит версию, при которой был построен; расхождение → отчёт устарел.
  const policiesVersion = ref(0);
  const lastVerification = ref<StoredVerification | null>(null);

  const verificationForCurrentCourse = computed<StoredVerification | null>(() => {
    const v = lastVerification.value;
    if (!v || v.courseId !== currentCourseId.value) return null;
    return v;
  });

  const verificationStale = computed<boolean>(() => {
    const v = verificationForCurrentCourse.value;
    if (!v) return false;
    return v.policiesVersionAtSave !== policiesVersion.value;
  });

  const saveVerification = (courseId: string, report: VerificationReport) => {
    lastVerification.value = {
      courseId,
      report,
      savedAt: Date.now(),
      policiesVersionAtSave: policiesVersion.value,
    };
  };

  /**
   * Загрузка метаданных: типы правил, статусы, компетенции, список курсов
   */
  const fetchMeta = async (force = false) => {
    if (isLoaded.value && !force) return;
    
    isLoading.value = true;
    error.value = null;
    
    try {
      const data = await getMeta();
      ruleTypes.value = data.rule_types;
      statuses.value = data.statuses;
      competencies.value = data.competencies;
      groups.value = data.groups || [];
      // Для селекта курса в Dashboard оставляем только курсы; остальные
      // элементы (модули/лекции/тесты) приезжают через getCourseTree
      courses.value = (data.course_elements || []).filter(
        (el) => (el.type || '').toLowerCase() === 'course',
      );
      isLoaded.value = true;
    } catch (e: any) {
      error.value = 'Ошибка загрузки метаданных онтологии';
      console.error(e);
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * Загрузка иерархии конкретного курса
   */
  const fetchCourseTree = async (courseId: string) => {
    isLoading.value = true;
    error.value = null;
    try {
      const data = await getCourseTree(courseId);
      currentCourseTree.value = data;
      currentCourseId.value = courseId;
    } catch (e: any) {
      error.value = e.message || 'Ошибка загрузки дерева курса';
      throw e;
    } finally {
      isLoading.value = false;
    }
  };

  const _findNodeById = (nodes: CourseTreeNode[], id: string): CourseTreeNode | null => {
    for (const node of nodes) {
      if (node.data.id === id) return node;
      if (node.children?.length) {
        const found = _findNodeById(node.children, id);
        if (found) return found;
      }
    }
    return null;
  };

  /**
   * Применить созданную или обновлённую политику к дереву: найти source-элемент
   * и пропатчить его data.policies, не перезагружая всё дерево.
   * Политика без source_element_id (вложенная в композит) не видна на дереве,
   * её игнорируем
   */
  const upsertPolicyInTree = (policy: PolicyResponse) => {
    const sourceId = policy.source_element_id;
    if (!sourceId || !currentCourseTree.value.length) return;
    const target = _findNodeById(currentCourseTree.value, sourceId);
    if (!target) return;
    const policies = (target.data.policies ??= []);
    const idx = policies.findIndex((p) => p.id === policy.id);
    if (idx >= 0) policies.splice(idx, 1, policy);
    else policies.push(policy);
    policiesVersion.value++;
  };

  const removePolicyFromTree = (policyId: string) => {
    if (!currentCourseTree.value.length) return;
    const walk = (nodes: CourseTreeNode[]): boolean => {
      for (const node of nodes) {
        const policies = node.data.policies;
        if (policies) {
          const idx = policies.findIndex((p) => p.id === policyId);
          if (idx >= 0) {
            policies.splice(idx, 1);
            return true;
          }
        }
        if (node.children?.length && walk(node.children)) return true;
      }
      return false;
    };
    if (walk(currentCourseTree.value)) {
      policiesVersion.value++;
    }
  };

  return {
    ruleTypes,
    statuses,
    competencies,
    groups,
    courses,
    currentCourseTree,
    currentCourseId,
    isLoading,
    error,
    isLoaded,
    policiesVersion,
    verificationForCurrentCourse,
    verificationStale,
    fetchMeta,
    fetchCourseTree,
    upsertPolicyInTree,
    removePolicyFromTree,
    saveVerification,
  };
});
