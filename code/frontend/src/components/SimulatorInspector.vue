<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue';
import { useSandboxStore } from '@/stores/sandbox';
import { useOntologyStore } from '@/stores/ontology';
import {
  ProgressStatusMap,
  ProgressStatusColorMap,
  ElementTypeMap,
  findNodeNameById,
  AggregateFunctionLabels,
} from '@/utils/formatters';
import { RuleType, ElementType, ProgressStatus } from '@/types/enums';
import BlockingExplanation from './BlockingExplanation.vue';

const props = defineProps<{
  selectedNode: any;
  courseTree: any[];
}>();

const sandboxStore = useSandboxStore();
const ontologyStore = useOntologyStore();

// Форма прохождения элемента
const simulateForm = reactive({
  status: ProgressStatus.COMPLETED as any,
  grade: null as number | null
});

// Выбор опций статуса в зависимости от типа элемента
const statusOptions = computed(() => {
  if (!props.selectedNode) return [];
  const type = props.selectedNode.data.type;
  if (type === ElementType.LECTURE) {
    return [
      { label: ProgressStatusMap[ProgressStatus.VIEWED], value: ProgressStatus.VIEWED },
      { label: ProgressStatusMap[ProgressStatus.COMPLETED], value: ProgressStatus.COMPLETED }
    ];
  }
  return [
    { label: ProgressStatusMap[ProgressStatus.COMPLETED], value: ProgressStatus.COMPLETED },
    { label: ProgressStatusMap[ProgressStatus.FAILED], value: ProgressStatus.FAILED }
  ];
});

// При смене элемента сбрасываем форму
watch(() => props.selectedNode, (newNode) => {
  if (newNode) {
    simulateForm.status = newNode.data.type === ElementType.LECTURE ? ProgressStatus.VIEWED : ProgressStatus.COMPLETED;
    simulateForm.grade = null;
  }
}, { immediate: true });

// Рекурсивный поиск имени целевого элемента
const getTargetName = (targetId: string) => {
  if (!targetId || !props.courseTree) return null;
  return findNodeNameById(props.courseTree, targetId);
};

const getCompetencyName = (compId: string) => {
  if (!compId) return null;
  const comp = ontologyStore.competencies.find(c => c.id === compId);
  return comp ? comp.name : null;
};

const getGroupName = (groupId: string) => {
  if (!groupId) return null;
  const g = ontologyStore.groups?.find((gr) => gr.id === groupId);
  return g ? g.name : groupId;
};

const formatDate = (dateString: string) => {
  if (!dateString) return '';
  const d = new Date(dateString);
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

/** Человечное описание одного условия для блока «Что нужно выполнить». */
const describePolicy = (pol: any): string => {
  switch (pol.rule_type) {
    case RuleType.COMPLETION_REQUIRED: {
      const t = getTargetName(pol.target_element_id) || pol.target_element_id;
      return `Завершить: ${t}`;
    }
    case RuleType.VIEWED_REQUIRED: {
      const t = getTargetName(pol.target_element_id) || pol.target_element_id;
      return `Просмотреть: ${t}`;
    }
    case RuleType.GRADE_REQUIRED: {
      const t = getTargetName(pol.target_element_id) || pol.target_element_id;
      return `Получить оценку не ниже ${pol.passing_threshold ?? '?'} за ${t}`;
    }
    case RuleType.COMPETENCY_REQUIRED: {
      const c = getCompetencyName(pol.competency_id || pol.target_competency_id);
      return `Получить компетенцию: ${c || pol.competency_id}`;
    }
    case RuleType.DATE_RESTRICTED: {
      const from = pol.valid_from ? `с ${formatDate(pol.valid_from)}` : '';
      const until = pol.valid_until ? ` по ${formatDate(pol.valid_until)}` : '';
      return `Доступно в период ${from}${until}`.trim();
    }
    case RuleType.GROUP_RESTRICTED: {
      return `Входить в группу: ${getGroupName(pol.restricted_to_group_id) || '—'}`;
    }
    case RuleType.AND_COMBINATION: {
      const n = pol.subpolicy_ids?.length ?? 0;
      return `Выполнить ВСЕ ${n} связанных условий (составное правило)`;
    }
    case RuleType.OR_COMBINATION: {
      const n = pol.subpolicy_ids?.length ?? 0;
      return `Выполнить ЛЮБОЕ из ${n} связанных условий (составное правило)`;
    }
    case RuleType.AGGREGATE_REQUIRED: {
      const fn = AggregateFunctionLabels[pol.aggregate_function] || pol.aggregate_function;
      const cnt = pol.aggregate_element_ids?.length ?? 0;
      return `${fn} по ${cnt} элементам не ниже ${pol.passing_threshold ?? '?'}`;
    }
    default:
      return pol.rule_type;
  }
};

const explanationVisible = ref(false);
const sandboxStudentId = 'sandbox';

const openExplanation = () => {
  explanationVisible.value = true;
};

// Отправка результата симуляции
const submitSimulation = async () => {
  if (!props.selectedNode) return;
  
  await sandboxStore.simulateProgress({
    element_id: props.selectedNode.data.id,
    status: simulateForm.status,
    grade: simulateForm.grade || undefined
  });
};
</script>

<template>
  <div v-if="!selectedNode" class="border-gray-300 flex flex-col items-center justify-center text-gray-400 h-full">
    <i class="pi pi-arrow-left text-4xl mb-4"></i>
    <p>Выберите учебный элемент в дереве слева для симуляции</p>
  </div>
  
  <div v-else class="bg-white rounded-xl flex flex-col gap-6">
    <div class="flex justify-between items-start">
      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-3">
          <h2 class="text-2xl font-bold text-gray-800">{{ selectedNode.label || selectedNode.data.name }}</h2>
        </div>
        <div class="flex gap-2 items-center">
          <Tag :value="ElementTypeMap[selectedNode.data.type as ElementType]" severity="secondary" class="uppercase font text-[10px]" />
          <Badge v-if="selectedNode.data.is_required" value="Обязательный" severity="secondary" />
          <Badge v-else value="Необязательный" severity="secondary" />
          <span class="text-xs text-gray-400">ID: {{ selectedNode.data.id }}</span>
        </div>
      </div>
    </div>

    <!-- Блок блокировки -->
    <div v-if="selectedNode.data.is_locked" class="p-6 bg-gray-100 rounded-lg border border-gray-200 mt-2">
      <div class="flex items-center justify-between gap-3 text-gray-700 font-bold mb-2">
        <span class="flex items-center gap-3">
          <i class="pi pi-lock text-xl text-gray-500"></i>
          Элемент заблокирован политиками доступа
        </span>
        <Button
          icon="pi pi-info-circle"
          label="Объяснить"
          size="small"
          severity="secondary"
          variant="outlined"
          @click="openExplanation"
        />
      </div>
      <p class="text-sm text-gray-600 mb-3">
        Для получения доступа необходимо выполнить требования:
      </p>
      
      <ul v-if="selectedNode.data.policies && selectedNode.data.policies.length" class="list-disc pl-5 text-sm text-gray-700 mt-2 space-y-1">
        <li v-for="pol in selectedNode.data.policies" :key="pol.id">
          {{ describePolicy(pol) }}
        </li>
      </ul>
      <div v-else class="text-xs italic text-gray-400">
        <ul class="list-disc pl-5 text-sm text-gray-600 space-y-1">
          <li><span class="font-semibold text-gray-700">Разблокировка родительского элемента.</span></li>
        </ul>
      </div>
    </div>

    <!-- Блокировка Агрегатов -->
    <div v-else-if="[ElementType.COURSE, ElementType.MODULE].includes(selectedNode.data.type)">
      <div class="p-4 bg-surface-50 rounded-lg border border-surface-200 border-dashed text-gray-500">
        <div class="flex items-center gap-3">
          <i class="pi pi-info-circle"></i>
          Прогресс модулей и курсов вычисляется автоматически.
          <br>
          Проходите лекции и тесты внутри, чтобы завершить этот уровень.
        </div>
      </div>
    </div>
    
    <!-- Форма симуляции (только для атомарных элементов и если не завершено) -->
    <Card v-else class="bg-gray-100 border border-gray-100 shadow-none overflow-hidden">
      <template #title>
        <div class="text-gray-800 text-lg flex items-center gap-2">
           Эмуляция прохождения
        </div>
      </template>
      <template #content>
         <div class="flex flex-row flex-wrap items-end gap-4">
           <div class="flex flex-col gap-2 min-w-[150px]">
             <label class="text-xs font-semibold text-gray-400 uppercase">Статус</label>
             <Select 
               v-model="simulateForm.status" 
               :options="statusOptions" 
               optionLabel="label" 
               optionValue="value" 
               class="w-full"
             />
           </div>
           
           <div v-if="[ElementType.TEST, ElementType.ASSIGNMENT, ElementType.PRACTICE].includes(selectedNode.data.type)" class="flex flex-col gap-1">
              <label class="text-xs font-semibold text-gray-400 uppercase">Оценка</label>
              <InputNumber 
                 v-model="simulateForm.grade" 
                 placeholder="0-100" 
                 :min="0"
                 :max="100"
                 class="w-24"
                 inputClass="w-full"
              />
            </div>

            <Button 
             label="Записать" 
             icon="pi pi-check" 
             @click="submitSimulation" 
             :loading="sandboxStore.isLoading"
             :disabled="selectedNode.data.is_locked" 
             class="h-10"
           />
         </div>
      </template>
    </Card>
    
    <div 
      v-if="![ElementType.COURSE, ElementType.MODULE].includes(selectedNode.data.type) && selectedNode.data.progress_status"
      class="flex justify-between items-center border-t border-gray-100 pt-4"
      >
      <div class="flex items-center gap-2">
        <p class="text-sm text-gray-500 mr-1">
          Прогресс:
        </p>
        <Badge 
          v-if="selectedNode.data.progress_status" 
          :value="ProgressStatusMap[selectedNode.data.progress_status as ProgressStatus]" 
          :severity="ProgressStatusColorMap[selectedNode.data.progress_status as ProgressStatus]"
        />
        <Badge 
          v-if="selectedNode.data.grade !== undefined && selectedNode.data.grade !== null" 
          :value="`Оценка: ${selectedNode.data.grade}`" 
          severity="secondary" 
        />
      </div>
      <Button
        label="Сбросить"
        severity="danger"
        variant="text"
        icon="pi pi-refresh"
        @click="sandboxStore.rollbackProgress(selectedNode.data.id)"
        :loading="sandboxStore.isLoading"
      />
    </div>

    <BlockingExplanation
      v-if="selectedNode"
      v-model:visible="explanationVisible"
      :student-id="sandboxStudentId"
      :element-id="selectedNode.data.id"
    />
  </div>
</template>
