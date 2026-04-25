<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue';
import { useOntologyStore } from '@/stores/ontology';
import { useSandboxStore } from '@/stores/sandbox';
import { useCourseTree } from '@/composables/useCourseTree';
import SandboxInspector from '@/components/SandboxInspector.vue';
import { useConfirm } from 'primevue/useconfirm';
import ConfirmDialog from 'primevue/confirmdialog';
import { buildCompetencyTree, buildGroupTree } from '@/utils/formatters';

// Сторы для работы с данными
const ontologyStore = useOntologyStore();
const sandboxStore = useSandboxStore();
const confirm = useConfirm();

// Состояние дерева через композабл
const { selectedNode, selectedNodeKey, expandedKeys, onNodeSelect } = useCourseTree(() => ontologyStore.currentCourseTree);


// При загрузке — метаданные курсов и текущее состояние песочницы
onMounted(async () => {
  if (ontologyStore.courses.length === 0) {
    await ontologyStore.fetchMeta();
  }
  if (ontologyStore.currentCourseId) {
    await loadCourseData(ontologyStore.currentCourseId);
  }
});

const loadCourseData = async (courseId: string) => {
  await ontologyStore.fetchCourseTree(courseId);
  await sandboxStore.syncTreeWithSandbox();
  selectedNode.value = null;
  selectedNodeKey.value = {};
};

// При смене курса подгружаем его дерево и накладываем песочницу
watch(() => ontologyStore.currentCourseId, async (newId) => {
  if (newId) {
    await loadCourseData(newId);
  }
});

// Реактивное дерево
const competencyTree = computed(() => buildCompetencyTree(ontologyStore.competencies || []));
const groupTree = computed(() => buildGroupTree(ontologyStore.groups || []));

// Состояние для TreeSelect (формат: { 'id1': { checked: true, partialChecked: false } })
const selectedCompetenciesMap = ref<Record<string, any>>({});
const selectedGroupsMap = ref<Record<string, any>>({});

// Синхронизация стора -> в TreeSelect (групп)
watch(() => sandboxStore.currentGroupIds, (newVal) => {
  const newMap: Record<string, any> = {};
  (newVal || []).forEach((id) => {
    newMap[id] = { checked: true, partialChecked: false };
  });
  selectedGroupsMap.value = newMap;
}, { immediate: true, deep: true });

const collectGroupAncestorIds = (groupId: string): string[] => {
  const ancestors: string[] = [];
  let current = ontologyStore.groups?.find((g) => g.id === groupId);
  while (current?.parent_id) {
    ancestors.push(current.parent_id);
    current = ontologyStore.groups?.find((g) => g.id === current!.parent_id);
  }
  return ancestors;
};

const onGroupNodeSelect = (node: any) => {
  const id = node?.data?.id ?? node?.key;
  if (!id) return;
  for (const ancestorId of collectGroupAncestorIds(id)) {
    selectedGroupsMap.value[ancestorId] = { checked: true, partialChecked: false };
  }
};

const onGroupsHide = () => {
  const selectedIds = Object.keys(selectedGroupsMap.value).filter(
    (key) => selectedGroupsMap.value[key].checked,
  );
  const current = new Set(sandboxStore.currentGroupIds);
  const changed =
    current.size !== selectedIds.length
    || selectedIds.some((id) => !current.has(id));
  if (changed) {
    sandboxStore.setGroups(selectedIds);
  }
};

// Синхронизация стора -> в TreeSelect
watch(() => sandboxStore.activeCompetencies, (newVal) => {
  const newMap: Record<string, any> = {};
  if (newVal && newVal.length) {
    newVal.forEach(id => {
      newMap[id] = { checked: true, partialChecked: false };
    });
  }
  selectedCompetenciesMap.value = newMap;
}, { immediate: true, deep: true });

const collectAncestorIds = (compId: string): string[] => {
  const ancestors: string[] = [];
  let current = ontologyStore.competencies.find((c) => c.id === compId);
  while (current?.parent_id) {
    ancestors.push(current.parent_id);
    current = ontologyStore.competencies.find((c) => c.id === current!.parent_id);
  }
  return ancestors;
};

const onCompNodeSelect = (node: any) => {
  const id = node?.data?.id ?? node?.key;
  if (!id) return;
  for (const ancestorId of collectAncestorIds(id)) {
    selectedCompetenciesMap.value[ancestorId] = { checked: true, partialChecked: false };
  }
};

const onCompetenciesHide = () => {
  const selectedIds = Object.keys(selectedCompetenciesMap.value).filter(
    key => selectedCompetenciesMap.value[key].checked
  );

  const current = new Set(sandboxStore.activeCompetencies);
  const changed =
    current.size !== selectedIds.length
    || selectedIds.some((id) => !current.has(id));
  if (changed) {
    sandboxStore.setCompetencies(selectedIds);
  }
};

const confirmReset = (event: Event) => {
    confirm.require({
        target: event.currentTarget as HTMLElement,
        message: 'Вы уверены, что хотите удалить весь прогресс тестового студента? Это действие необратимо.',
        header: 'Подтверждение сброса',
        icon: 'pi pi-exclamation-triangle',
        acceptClass: 'p-button-danger',
        acceptLabel: 'Да, удалить всё',
        rejectClass: 'p-button-secondary',
        rejectLabel: 'Отмена',
        accept: () => {
            sandboxStore.resetSandbox();
        }
    });
};
</script>

<template>
  <div class="flex flex-col gap-4 max-w-6xl mx-auto">
    <!-- Header: Selection and Config -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap justify-between items-center gap-4">
      <div class="flex flex-wrap items-center gap-6">
        <div class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Выбор курса</label>
          <Select
            v-model="ontologyStore.currentCourseId"
            :options="ontologyStore.courses"
            optionLabel="name"
            optionValue="id"
            placeholder="Выберите курс"
            emptyMessage="Нет доступных курсов"
            filter
            filterPlaceholder="Поиск курса..."
            class="w-80"
          />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Компетенции студента</label>
          <TreeSelect
            v-model="selectedCompetenciesMap"
            :options="competencyTree"
            selectionMode="checkbox"
            placeholder="Выберите навыки"
            emptyMessage="Нет данных"
            filter
            class="w-72"
            display="chip"
            @node-select="onCompNodeSelect"
            @hide="onCompetenciesHide"
          />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Группы</label>
          <TreeSelect
            v-model="selectedGroupsMap"
            :options="groupTree"
            selectionMode="checkbox"
            placeholder="Без групп"
            emptyMessage="В онтологии нет групп"
            filter
            class="w-72"
            display="chip"
            @node-select="onGroupNodeSelect"
            @hide="onGroupsHide"
          />
        </div>
      </div>
      
      <Button 
        label="Сбросить всё" 
        severity="danger" 
        variant="text"
        icon="pi pi-trash" 
        @click="confirmReset($event)" 
        :loading="sandboxStore.isLoading" 
      />
    </div>

    <!-- Main Content Area -->
    <div class="grid grid-cols-5 md:grid-cols-5 gap-4 h-[calc(100vh-156px)]">
      <!-- Left: Navigation Tree -->
      <div class="col-span-2 bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex flex-col h-full overflow-hidden">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2">
          Дерево курса
        </h3>
        
        <div class="overflow-y-auto flex-1 custom-scrollbar pr-2">
            <Tree 
              v-model:expandedKeys="expandedKeys"
              :value="ontologyStore.currentCourseTree" 
              selectionMode="single" 
              v-model:selectionKeys="selectedNodeKey" 
              @nodeSelect="onNodeSelect"
              class="w-full border-none p-0"
              :loading="ontologyStore.isLoading"
            >
              <template #default="slotProps">
                 <div class="flex items-center gap-2 py-1.5 w-full overflow-hidden" :class="{'opacity-50 grayscale': sandboxStore.isElementLocked(slotProps.node.data.id)}">

                    <div class="shrink-0">
                      <i v-if="sandboxStore.progressById[slotProps.node.data.id]?.status === 'completed'" class="pi pi-check-circle text-green-500 text-md"></i>
                      <i v-else-if="sandboxStore.progressById[slotProps.node.data.id]?.status === 'failed'" class="pi pi-times-circle text-red-500 text-md"></i>
                      <i v-else-if="sandboxStore.isElementLocked(slotProps.node.data.id)" class="pi pi-lock text-surface-400 text-md"></i>
                    </div>
                  
                   <span class="flex-1 min-w-0 break-words leading-tight pr-2" :class="[
                      {'font-semibold text-surface-900': slotProps.node.data.type === 'module'},
                   ]">
                     {{ slotProps.node.label || slotProps.node.data.name }}
                   </span>
                 </div>
              </template>
              <template #empty>
                <div class="p-4 text-center text-gray-500">Нет данных для отображения</div>
              </template>
            </Tree>
        </div>
      </div>

      <!-- Right: Element Details & Emulation -->
      <div class="col-span-3 bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col h-full overflow-y-auto custom-scrollbar">
         <SandboxInspector 
            :selected-node="selectedNode" 
            :course-tree="ontologyStore.currentCourseTree" 
         />
      </div>
    </div>
    <ConfirmDialog :style="{ width: '600px' }"></ConfirmDialog>
  </div>
</template>
