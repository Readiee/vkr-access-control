<script setup lang="ts">
import { computed, ref } from 'vue';
import { RuleType } from '@/types';
import type { PolicyCreate, PolicyResponse, CourseTreeNode } from '@/types';
import { useOntologyStore } from '@/stores/ontology';
import { ruleTypeOptions, RuleTypeMap, findNodeNameById, formatPolicyBadgeText } from '@/utils/formatters';
import { useTreeHelpers } from '@/composables/useTreeHelpers';
import { usePolicyForm } from '@/composables/usePolicyForm';
import { useConfirm } from 'primevue/useconfirm';
import { createPolicy, updatePolicy, deletePolicy } from '@/api';
import { toastService } from '@/utils/toastService';


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
    if (props.editMode && props.initialData?.id) {
      await updatePolicy(props.initialData.id, payload);
      toastService.showSuccess('Правило обновлено');
    } else {
      await createPolicy(payload);
      toastService.showSuccess('Правило создано');
    }
    await store.fetchCourseTree(store.currentCourseId || '');
    isEditing.value = false;
    emit('saved');
  } catch (err) {
    toastService.showError('Ошибка при сохранении правила');
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
        await store.fetchCourseTree(store.currentCourseId || '');
        emit('saved');
      } catch (err) {
        toastService.showError('Ошибка при удалении');
      }
    }
  });
};

const isFormValid = computed(() => {
  const f = form.value;
  if (f.rule_type === RuleType.COMPETENCY_REQUIRED) return !!f.target_competency_id;
  if (f.rule_type === RuleType.DATE_RESTRICTED) {
    if (!f.available_from && !f.available_until) return false;
    if (f.available_from && f.available_until) return f.available_from < f.available_until;
    return true;
  }
  return !!f.target_element_id;
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

        <!-- Режим редактирования -->
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
                  :options="ruleTypeOptions"
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
           </div>

           <div v-if="isDateRule" class="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2 border-t border-surface-50">
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Доступно С</label>
                <DatePicker v-model="form.available_from" manualInput showTime hourFormat="24" dateFormat="dd.mm.yy" class="w-full" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Доступно ПО</label>
                <DatePicker v-model="form.available_until" manualInput showTime hourFormat="24" dateFormat="dd.mm.yy" class="w-full" />
              </div>
           </div>

           <div class="flex justify-between items-center pt-2 border-t border-surface-50">
              <div class="flex items-center gap-3">
                <ToggleSwitch v-model="form.is_active" inputId="isActiveSwitch" size="small" />
                <label for="isActiveSwitch" class="text-xs font-medium text-surface-600">{{ form.is_active ? 'Активно' : 'Выключено' }}</label>
              </div>
              <div class="flex gap-4">
                <Button v-if="!editMode" label="Отмена" severity="secondary" variant="text" size="small" @click="$emit('cancelled')" />
                <Button :label="editMode ? 'Сохранить' : 'Добавить'" size="small" :icon="editMode ? 'pi pi-check' : 'pi pi-plus'" @click="submitForm" :loading="isSaving" :disabled="!isFormValid" />
              </div>
           </div>
        </div>

      </div>
    </template>
  </Card>
</template>
