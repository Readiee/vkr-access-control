import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  getSandboxState,
  listSandboxStudents,
  resetSandbox as apiResetSandbox,
  rollbackSandboxProgress,
  setSandboxCompetencies,
  simulateSandboxProgress,
} from '@/api/sandbox';
import type { SandboxProgressEntry, SandboxProgressPayload, SandboxStudent } from '@/types';
import { useOntologyStore } from '@/stores/ontology';
import { toastService } from '@/utils/toastService';

export const useSandboxStore = defineStore('sandbox', () => {
  const ontologyStore = useOntologyStore();

  const isLoading = ref(false);
  const students = ref<SandboxStudent[]>([]);
  const currentStudentId = ref<string | null>(null);
  const currentStudentName = ref<string>('');
  const activeCompetencies = ref<string[]>([]);

  // Runtime-оверлей над ontology.currentCourseTree: что доступно студенту сейчас
  // и какой прогресс по какому элементу. Храним отдельно, не мутируя дерево онтологии.
  const availableElementIds = ref<Set<string>>(new Set());
  const progressById = ref<Record<string, SandboxProgressEntry>>({});

  const isElementLocked = (elementId: string): boolean => {
    if (!elementId) return false;
    if (progressById.value[elementId]) return false;
    return !availableElementIds.value.has(elementId);
  };

  const lockedIds = computed<Set<string>>(() => {
    const out = new Set<string>();
    const tree = ontologyStore.currentCourseTree;
    if (!tree) return out;
    const walk = (nodes: typeof tree) => {
      for (const node of nodes) {
        if (isElementLocked(node.data.id)) out.add(node.data.id);
        if (node.children?.length) walk(node.children);
      }
    };
    walk(tree);
    return out;
  });

  const loadStudents = async () => {
    students.value = await listSandboxStudents();
    if (!currentStudentId.value && students.value.length) {
      currentStudentId.value = students.value[0].id;
    }
  };

  const selectStudent = async (id: string) => {
    currentStudentId.value = id;
    await syncTreeWithSandbox();
  };

  const syncTreeWithSandbox = async () => {
    const courseId = ontologyStore.currentCourseId;
    if (!courseId) return;

    try {
      const state = await getSandboxState(courseId, currentStudentId.value);
      availableElementIds.value = new Set(state.available_elements);
      progressById.value = state.progress ?? {};
      activeCompetencies.value = state.active_competencies ?? [];
      if (state.student_id) currentStudentId.value = state.student_id;
      if (state.student_name) currentStudentName.value = state.student_name;
    } catch (e) {
      console.error('Ошибка при синхронизации состояния песочницы', e);
    }
  };

  const refreshCourseData = async () => {
    if (ontologyStore.currentCourseId) {
      await syncTreeWithSandbox();
    }
  };

  const simulateProgress = async (payload: SandboxProgressPayload) => {
    isLoading.value = true;
    try {
      await simulateSandboxProgress(payload, currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess(`Статус элемента ${payload.element_id} обновлен`);
    } finally {
      isLoading.value = false;
    }
  };

  const rollbackProgress = async (elementId: string) => {
    isLoading.value = true;
    try {
      await rollbackSandboxProgress(elementId, currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess(`Прогресс для ${elementId} откачен`);
    } finally {
      isLoading.value = false;
    }
  };

  const resetSandbox = async () => {
    isLoading.value = true;
    try {
      await apiResetSandbox(currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess('Песочница полностью очищена');
    } finally {
      isLoading.value = false;
    }
  };

  const setCompetencies = async (competencyIds: string[]) => {
    isLoading.value = true;
    try {
      await setSandboxCompetencies(competencyIds, currentStudentId.value);
      await refreshCourseData();
      toastService.showSuccess('Компетенции обновлены');
    } finally {
      isLoading.value = false;
    }
  };

  return {
    isLoading,
    students,
    currentStudentId,
    currentStudentName,
    activeCompetencies,
    progressById,
    lockedIds,
    isElementLocked,
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
