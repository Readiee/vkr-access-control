import { defineStore } from 'pinia';
import { ref } from 'vue';
import { SandboxAPI, type SandboxProgressPayload, type SandboxStudent } from '@/api/sandbox';
import { useOntologyStore } from '@/stores/ontology';
import { toastService } from '@/utils/toastService';

export const useSandboxStore = defineStore('sandbox', () => {
  const isLoading = ref(false);
  const ontologyStore = useOntologyStore();
  const activeCompetencies = ref<string[]>([]);
  const students = ref<SandboxStudent[]>([]);
  const currentStudentId = ref<string | null>(null);
  const currentStudentName = ref<string>('');

  const loadStudents = async () => {
    students.value = await SandboxAPI.listStudents();
    if (!currentStudentId.value && students.value.length) {
      currentStudentId.value = students.value[0].id;
    }
  };

  const selectStudent = async (id: string) => {
    currentStudentId.value = id;
    await syncTreeWithSandbox();
  };

  /**
   * Синхронизация дерева с бэкендом (доступы и статусы)
   */
  const syncTreeWithSandbox = async () => {
    const courseId = ontologyStore.currentCourseId;
    if (!courseId || !ontologyStore.currentCourseTree) return;

    try {
      const state = await SandboxAPI.getState(courseId, currentStudentId.value);
      const { available_elements, progress, active_competencies, student_name, student_id } = state;

      activeCompetencies.value = active_competencies || [];
      if (student_id) currentStudentId.value = student_id;
      if (student_name) currentStudentName.value = student_name;

      // Рекурсивный хелпер для обогащения узлов
      const enrichNodes = (nodes: any[]) => {
        for (const node of nodes) {
          const elId = node.data.id;
          const hasProgress = !!progress[elId];
          
          // Элемент заблокирован, если он недоступен И еще не пройден
          node.data.is_locked = !available_elements.includes(elId) && !hasProgress;
          
          // Проставляем прогресс
          if (hasProgress) {
            node.data.progress_status = progress[elId].status;
            node.data.grade = progress[elId].grade;
          } else {
            node.data.progress_status = null;
            node.data.grade = null;
          }

          if (node.children && node.children.length > 0) {
            enrichNodes(node.children);
          }
        }
      };

      // Мутируем текущее реактивное дерево
      enrichNodes(ontologyStore.currentCourseTree);
      
    } catch (e) {
      console.error("Ошибка при синхронизации состояния Песочницы", e);
    }
  };

  /**
   * Обновляет динамические данные (статусы/доступность) без перезагрузки всего дерева.
   */
  const refreshCourseData = async () => {
    if (ontologyStore.currentCourseId) {
      await syncTreeWithSandbox();
    }
  };

  /**
   * Симуляция прохождения учебного элемента.
   */
  const simulateProgress = async (payload: SandboxProgressPayload) => {
    isLoading.value = true;
    try {
      await SandboxAPI.simulateProgress(payload, currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess(`Статус элемента ${payload.element_id} обновлен`);
    } catch (error) {
      console.error('Ошибка симуляции:', error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  const rollbackProgress = async (elementId: string) => {
    isLoading.value = true;
    try {
      await SandboxAPI.rollbackProgress(elementId, currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess(`Прогресс для ${elementId} откачен`);
    } catch (error) {
      console.error('Ошибка отката:', error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  const resetSandbox = async () => {
    isLoading.value = true;
    try {
      await SandboxAPI.resetAll(currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess('Песочница полностью очищена');
    } catch (error) {
      console.error('Ошибка сброса песочницы:', error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  const setCompetencies = async (competencyIds: string[]) => {
    isLoading.value = true;
    try {
      await SandboxAPI.setCompetencies(competencyIds, currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess(`Компетенции обновлены`);
    } catch (error) {
      console.error(error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  return {
    isLoading,
    activeCompetencies,
    students,
    currentStudentId,
    currentStudentName,
    loadStudents,
    selectStudent,
    syncTreeWithSandbox,
    refreshCourseData,
    simulateProgress,
    rollbackProgress,
    resetSandbox,
    setCompetencies,
  };
});
