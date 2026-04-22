import { defineStore } from 'pinia';
import { ref } from 'vue';
import { getMeta, getCourseTree } from '@/api';
import type { Competency, CourseElement, CourseTreeNode, Group } from '@/types';

export const useOntologyStore = defineStore('ontology', () => {
  // --- State ---
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

  // --- Actions ---

  /**
   * Загрузка метаданных (типы, статусы, компетенции, список курсов).
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
      // Просто подставляем данные, фильтрация теперь на бэкенде
      courses.value = data.course_elements || [];
      isLoaded.value = true;
    } catch (e: any) {
      error.value = 'Ошибка загрузки метаданных онтологии';
      console.error(e);
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * Загрузка иерархии конкретного курса.
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
    fetchMeta,
    fetchCourseTree
  };
});
