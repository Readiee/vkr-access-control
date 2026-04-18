import { defineStore } from 'pinia';
import { ref } from 'vue';
import { SandboxAPI, type SandboxProgressPayload } from '@/api/sandbox';
import { useOntologyStore } from '@/stores/ontology';
import { toastService } from '@/utils/toastService';

export const useSandboxStore = defineStore('sandbox', () => {
  const isLoading = ref(false);
  const ontologyStore = useOntologyStore();
  const activeCompetencies = ref<string[]>([]);
  
  /**
   * Синхронизация дерева с бэкендом (доступы и статусы)
   */
  const syncTreeWithSandbox = async () => {
    const courseId = ontologyStore.currentCourseId;
    if (!courseId || !ontologyStore.currentCourseTree) return;

    try {
      const state = await SandboxAPI.getState(courseId);
      const { available_elements, progress, active_competencies } = state;

      // Синхронизируем компетенции
      activeCompetencies.value = active_competencies || [];

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
      await SandboxAPI.simulateProgress(payload);
      await refreshCourseData();
      toastService.showSuccess(`Статус элемента ${payload.element_id} обновлен`);
    } catch (error) {
      console.error('Ошибка симуляции:', error);
      // Ошибка уже показана через перехватчик в apiClient
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * Откат прохождения (удаление рекорда).
   */
  const rollbackProgress = async (elementId: string) => {
    isLoading.value = true;
    try {
      await SandboxAPI.rollbackProgress(elementId);
      await refreshCourseData();
      toastService.showSuccess(`Прогресс для ${elementId} откачен`);
    } catch (error) {
      console.error('Ошибка отката:', error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * Полный сброс прогресса и компетенций Sandbox-студента.
   */
  const resetSandbox = async () => {
    isLoading.value = true;
    try {
      await SandboxAPI.resetAll();
      await refreshCourseData();
      toastService.showSuccess('Песочница полностью очищена');
    } catch (error) {
      console.error('Ошибка сброса песочницы:', error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  };

  /**
   * Установка списка компетенций.
   */
  const setCompetencies = async (competencyIds: string[]) => {
    isLoading.value = true;
    try {
      await SandboxAPI.setCompetencies(competencyIds);
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
    syncTreeWithSandbox,
    refreshCourseData,
    simulateProgress,
    rollbackProgress,
    resetSandbox,
    setCompetencies
  };
});
