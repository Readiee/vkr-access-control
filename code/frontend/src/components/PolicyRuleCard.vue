<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { AggregateFunction, RuleType } from '@/types';
import type { PolicyCreate, PolicyResponse, CourseTreeNode } from '@/types';
import { useOntologyStore } from '@/stores/ontology';
import {
  ruleTypeOptions,
  RuleTypeMap,
  findNodeNameById,
  formatPolicyBadgeText,
  AggregateFunctionLabels,
  GRADABLE_ELEMENT_TYPES,
} from '@/utils/formatters';
import { useTreeHelpers } from '@/composables/useTreeHelpers';
import { usePolicyForm } from '@/composables/usePolicyForm';
import { useConfirm } from 'primevue/useconfirm';
import { createPolicy, getPolicies, updatePolicy, deletePolicy } from '@/api';
import { toastService } from '@/utils/toastService';
import CompositePolicyEditor from './CompositePolicyEditor.vue';


const props = defineProps<{
  targetNode: any;
  treeData?: CourseTreeNode[];
  editMode?: boolean;
  initialData?: PolicyResponse | null;
}>();

const emit = defineEmits<{
  (e: 'saved'): void;
  (e: 'cancelled'): void;
}>();

const store = useOntologyStore();
const confirm = useConfirm();
const { getBlockedIds, getExpandedKeys, buildSelectableTree } = useTreeHelpers();

const isEditing = ref(!props.editMode);

// Адаптация для usePolicyForm
const formEmit = (event: string, data: any) => {
  if (event === 'submit') handleFinalSubmit(data);
  if (event === 'delete') handleFinalDelete(data);
};

const { form, treeSelectModel, submitForm } = usePolicyForm(props, formEmit);

const isSaving = ref(false);

const handleFinalSubmit = async (payload: PolicyCreate) => {
  isSaving.value = true;
  payload.source_element_id = props.targetNode?.data?.id || payload.source_element_id;

  try {
    let saved: PolicyResponse;
    if (props.editMode && props.initialData?.id) {
      saved = await updatePolicy(props.initialData.id, payload);
      toastService.showSuccess('Правило обновлено');
    } else {
      saved = await createPolicy(payload);
      toastService.showSuccess('Правило создано');
    }
    store.upsertPolicyInTree(saved);
    isEditing.value = false;
    emit('saved');
  } catch {
    // toast с текстом ошибки уже показал axios interceptor
  } finally {
    isSaving.value = false;
  }
};

const handleFinalDelete = (policyId: string) => {
  confirm.require({
    message: 'Вы уверены, что хотите удалить это правило?',
    header: 'Подтверждение удаления',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: {
      label: 'Отмена',
      severity: 'secondary',
      outlined: true
    },
    acceptProps: {
      label: 'Удалить',
      severity: 'danger'
    },
    accept: async () => {
      try {
        await deletePolicy(policyId);
        toastService.showInfo('Правило удалено');
        store.removePolicyFromTree(policyId);
        emit('saved');
      } catch {
        // toast с текстом ошибки уже показал axios interceptor
      }
    }
  });
};

/** Первая невыполненная валидация — то, что показываем методисту, чтобы он
 *  понимал, почему кнопка disabled. Пустая строка — форма валидна. */
const validationHint = computed<string>(() => {
  const f = form.value;
  switch (f.rule_type) {
    case RuleType.COMPLETION_REQUIRED:
    case RuleType.VIEWED_REQUIRED:
      return f.target_element_id ? '' : 'Выберите целевой элемент';
    case RuleType.GRADE_REQUIRED:
      if (!f.target_element_id) return 'Выберите целевой элемент';
      if (f.passing_threshold == null) return 'Задайте минимальный балл (0–100)';
      return '';
    case RuleType.COMPETENCY_REQUIRED:
      return f.target_competency_id ? '' : 'Выберите требуемую компетенцию';
    case RuleType.DATE_RESTRICTED:
      if (!f.valid_from) return 'Задайте дату начала доступа';
      if (!f.valid_until) return 'Задайте дату окончания доступа';
      if (f.valid_from >= f.valid_until) return 'Дата начала должна быть раньше даты окончания';
      return '';
    case RuleType.GROUP_RESTRICTED:
      return f.restricted_to_group_id ? '' : 'Выберите группу студентов';
    case RuleType.AND_COMBINATION:
    case RuleType.OR_COMBINATION: {
      const subs = Array.isArray(f.subpolicy_ids) ? f.subpolicy_ids : [];
      if (new Set(subs).size < 2) return 'Выберите не менее 2 подусловий';
      return '';
    }
    case RuleType.AGGREGATE_REQUIRED:
      if (!f.aggregate_function) return 'Выберите функцию агрегирования';
      if (!Array.isArray(f.aggregate_element_ids) || !f.aggregate_element_ids.length)
        return 'Выберите хотя бы один элемент с оценкой';
      if (f.passing_threshold == null) return 'Задайте минимальный балл (0–100)';
      return '';
    default:
      return '';
  }
});

const isFormValid = computed(() => validationHint.value === '');

const isGroupRule = computed(() => form.value.rule_type === RuleType.GROUP_RESTRICTED);
const isCompositeRule = computed(
  () => form.value.rule_type === RuleType.AND_COMBINATION
    || form.value.rule_type === RuleType.OR_COMBINATION,
);
const isAggregateRule = computed(() => form.value.rule_type === RuleType.AGGREGATE_REQUIRED);

const atomicRuleTypeOptions = ruleTypeOptions.filter((o) =>
  o.value !== RuleType.AND_COMBINATION && o.value !== RuleType.OR_COMBINATION,
);

const aggregateFunctionOptions = Object.values(AggregateFunction).map((fn) => ({
  label: AggregateFunctionLabels[fn] ?? fn,
  value: fn,
}));

const availableSubpolicies = ref<PolicyResponse[]>([]);

type ElementOption = { id: string; name: string; type: string };

const flattenElements = (nodes: CourseTreeNode[] | undefined): ElementOption[] => {
  const out: ElementOption[] = [];
  const walk = (arr: CourseTreeNode[] | undefined) => {
    (arr || []).forEach((n) => {
      if (n.data?.id) {
        out.push({
          id: n.data.id,
          name: n.data.name,
          type: (n.data.type || '').toLowerCase(),
        });
      }
      if (n.children?.length) walk(n.children as any);
    });
  };
  walk(nodes);
  return out;
};

const courseElementOptions = computed(() => flattenElements(props.treeData));

const gradableElementOptions = computed(() =>
  courseElementOptions.value.filter((el) => GRADABLE_ELEMENT_TYPES.has(el.type)),
);

onMounted(async () => {
  try {
    availableSubpolicies.value = await getPolicies();
  } catch {
    availableSubpolicies.value = [];
  }
});

const subpolicyOptions = computed(() => {
  const selfId = props.initialData?.id;
  return availableSubpolicies.value
    .filter((p) => p.id !== selfId)
    .map((p) => ({
      id: p.id,
      label: `${p.id} · ${RuleTypeMap[p.rule_type]?.label ?? p.rule_type}`,
    }));
});

const expandedKeys = computed(() => getExpandedKeys(props.treeData ?? [], props.targetNode?.data?.id));

const selectableTreeNodes = computed(() => {
  if (!props.treeData) return [];
  const blocked = getBlockedIds(props.treeData, props.targetNode?.data?.id ?? '');
  return buildSelectableTree(props.treeData, blocked, form.value.rule_type, props.targetNode?.data?.id);
});

const requiresTargetElement = computed(() => {
  return [RuleType.COMPLETION_REQUIRED, RuleType.GRADE_REQUIRED, RuleType.VIEWED_REQUIRED].includes(form.value.rule_type as RuleType);
});

const isCompetencyRule = computed(() => form.value.rule_type === RuleType.COMPETENCY_REQUIRED);
const isGradeRule = computed(() => form.value.rule_type === RuleType.GRADE_REQUIRED);
const isDateRule = computed(() => form.value.rule_type === RuleType.DATE_RESTRICTED);
</script>

<template>
  <Card class="border border-surface-200 shadow-none overflow-hidden">
    <template #content>
      <div class="">
        
        <!-- Режим просмотра -->
        <div v-if="!isEditing && initialData" class="flex justify-between items-center group">
           <div class="flex items-center gap-4">
            <i class="pi pi-lock text-surface-400"></i>
             <div class="flex flex-col">
               <span class="text-sm font-medium text-surface-800" :class="{'text-surface-400 opacity-60': !form.is_active}">
                 {{ formatPolicyBadgeText(initialData, treeData || [], store.competencies) }}
               </span>
               <div class="flex items-center gap-1 mt-1">
                  <Tag 
                    :severity="RuleTypeMap[initialData.rule_type]?.severity" 
                    :value="RuleTypeMap[initialData.rule_type]?.label" 
                    rounded 
                    style="font-size: 0.7rem; padding: 0.1rem 0.4rem;"
                  />
                  <Tag v-if="!form.is_active" value="Выключено" rounded severity="secondary" style="font-size: 0.7rem; padding: 0.1rem 0.4rem;" />
               </div>
             </div>
           </div>
           <div class="flex gap-1">
             <Button icon="pi pi-pencil" text rounded size="small" @click="isEditing = true" v-tooltip.top="'Редактировать'" />
             <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="handleFinalDelete(initialData.id)" v-tooltip.top="'Удалить'" />
           </div>
        </div>

        <!-- Редактирование составного условия -->
        <CompositePolicyEditor
          v-else-if="editMode && initialData && (initialData.rule_type === RuleType.AND_COMBINATION || initialData.rule_type === RuleType.OR_COMBINATION)"
          :target-node="targetNode"
          :tree-data="treeData ?? []"
          :initial-data="initialData"
          @saved="isEditing = false; $emit('saved');"
          @cancelled="isEditing = false"
        />

        <!-- Режим редактирования атомарного правила -->
        <div v-else class="flex flex-col gap-5">
           <div class="flex justify-between items-center border-b border-surface-100 pb-3">
             <span class="font-bold text-xs text-surface-600 uppercase tracking-widest flex items-center gap-2">
               <i class="pi" :class="editMode ? 'pi-pencil' : 'pi-plus-circle'"></i>
               {{ editMode ? 'Редактирование правила' : 'Новое правило' }}
             </span>
             <Button v-if="editMode" icon="pi pi-times" text rounded size="small" @click="isEditing = false" />
           </div>

               <!-- Форма -->
           <div class="grid grid-cols-3 gap-5">
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Тип условия</label>
                <Select
                  v-model="form.rule_type"
                  :options="atomicRuleTypeOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>

              <div v-if="requiresTargetElement" class="flex flex-col gap-1 col-span-2">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Целевой элемент</label>
                <TreeSelect
                  v-model="treeSelectModel"
                  :options="selectableTreeNodes"
                  :expandedKeys="expandedKeys"
                  placeholder="Выберите элемент"
                  class="w-full"
                  selection-mode="single"
                >
                  <template #value>
                    <span v-if="form.target_element_id">
                      {{ findNodeNameById(treeData ?? [], form.target_element_id) ?? form.target_element_id }}
                    </span>
                    <span v-else class="text-surface-400">Выбор...</span>
                  </template>
                </TreeSelect>
              </div>

              <div v-if="isCompetencyRule" class="flex flex-col gap-1 col-span-2">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Требуемая компетенция</label>
                <Select
                  v-model="form.target_competency_id"
                  :options="store.competencies"
                  optionLabel="name"
                  optionValue="id"
                  placeholder="Выберите..."
                  class="w-full"
                />
              </div>

              <div v-if="isGradeRule" class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Мин. балл</label>
                <InputNumber v-model="form.passing_threshold" :min="0" :max="100" placeholder="0-100" class="w-20" inputClass="w-full" />
              </div>

              <div v-if="isAggregateRule" class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Функция</label>
                <Select
                  v-model="form.aggregate_function"
                  :options="aggregateFunctionOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>
              <div v-if="isAggregateRule" class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Мин. балл</label>
                <InputNumber v-model="form.passing_threshold" :min="0" :max="100" placeholder="0-100" class="w-20" inputClass="w-full" />
              </div>
           </div>

           <div v-if="isDateRule" class="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2 border-t border-surface-50">
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Доступно С</label>
                <DatePicker v-model="form.valid_from" manualInput showTime hourFormat="24" dateFormat="dd.mm.yy" class="w-full" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Доступно ПО</label>
                <DatePicker
                  v-model="form.valid_until"
                  manualInput showTime hourFormat="24" dateFormat="dd.mm.yy"
                  :minDate="form.valid_from || undefined"
                  class="w-full"
                />
              </div>
           </div>

           <div v-if="isGroupRule" class="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2 border-t border-surface-50">
              <div class="flex flex-col gap-1 col-span-2">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Группа студентов</label>
                <Select
                  v-model="form.restricted_to_group_id"
                  :options="store.groups"
                  optionLabel="name"
                  optionValue="id"
                  placeholder="Выберите группу"
                  emptyMessage="Нет групп в онтологии"
                  class="w-full"
                />
              </div>
           </div>

           <!--
             Форма композитов остаётся в режиме просмотра/редактирования существующих
             AND/OR-правил, но новые не создаются отсюда — используется отдельный flow.
           -->
           <div v-if="isCompositeRule && editMode" class="flex flex-col gap-3 pt-2 border-t border-surface-50">
              <label class="text-[11px] font-bold text-surface-500 uppercase">Подусловия</label>
              <MultiSelect
                v-model="form.subpolicy_ids"
                :options="subpolicyOptions"
                optionLabel="label"
                optionValue="id"
                display="chip"
                filter
                class="w-full"
              />
           </div>

           <div v-if="isAggregateRule" class="flex flex-col gap-1 pt-2 border-t border-surface-50">
              <label class="text-[11px] font-bold text-surface-500 uppercase">
                Элементы с оценками
              </label>
              <MultiSelect
                v-model="form.aggregate_element_ids"
                :options="gradableElementOptions"
                optionLabel="name"
                optionValue="id"
                placeholder="Выберите тесты/практики"
                display="chip"
                filter
                class="w-full"
              />
              <p class="text-[11px] text-surface-400 mt-1">
                Доступны только тесты, практики и задания (элементы, за которые ставится оценка).
              </p>
           </div>

           <div class="flex justify-between items-center pt-2 border-t border-surface-50">
              <div class="flex items-center gap-3">
                <ToggleSwitch v-model="form.is_active" inputId="isActiveSwitch" size="small" />
                <label for="isActiveSwitch" class="text-xs font-medium text-surface-600">{{ form.is_active ? 'Активно' : 'Выключено' }}</label>
              </div>
              <div class="flex items-center gap-4">
                <span v-if="validationHint" class="text-xs text-surface-500 italic">
                  <i class="pi pi-info-circle mr-1"></i>{{ validationHint }}
                </span>
                <Button v-if="!editMode" label="Отмена" severity="secondary" variant="text" size="small" @click="$emit('cancelled')" />
                <Button :label="editMode ? 'Сохранить' : 'Добавить'" size="small" :icon="editMode ? 'pi pi-check' : 'pi pi-plus'" @click="submitForm" :loading="isSaving" :disabled="!isFormValid" />
              </div>
           </div>
        </div>

      </div>
    </template>
  </Card>
</template>
