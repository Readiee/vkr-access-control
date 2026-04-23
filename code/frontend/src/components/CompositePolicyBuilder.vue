<script setup lang="ts">
import { computed, ref } from 'vue';
import { useOntologyStore } from '@/stores/ontology';
import { createPolicy } from '@/api';
import { toastService } from '@/utils/toastService';
import { RuleType, AggregateFunction } from '@/types';
import type { CourseTreeNode, PolicyCreate } from '@/types';
import {
  ruleTypeOptions,
  AggregateFunctionLabels,
  GRADABLE_ELEMENT_TYPES,
} from '@/utils/formatters';

const props = defineProps<{
  targetNode: any;
  treeData: CourseTreeNode[];
}>();

const emit = defineEmits<{
  (e: 'saved'): void;
  (e: 'cancelled'): void;
}>();

const store = useOntologyStore();
const isSaving = ref(false);

type ChildDraft = {
  _key: number;
  rule_type: RuleType;
  target_element_id?: string | null;
  target_competency_id?: string | null;
  passing_threshold?: number | null;
  valid_from?: Date | null;
  valid_until?: Date | null;
  restricted_to_group_id?: string | null;
  aggregate_function?: AggregateFunction | null;
  aggregate_element_ids?: string[] | null;
};

let nextKey = 1;
const newChild = (): ChildDraft => ({
  _key: nextKey++,
  rule_type: RuleType.COMPLETION_REQUIRED,
  target_element_id: null,
  passing_threshold: null,
});

const children = ref<ChildDraft[]>([newChild(), newChild()]);

const atomicRuleTypeOptions = ruleTypeOptions.filter(
  (o) => o.value !== RuleType.AND_COMBINATION && o.value !== RuleType.OR_COMBINATION,
);

const aggregateFunctionOptions = Object.values(AggregateFunction).map((fn) => ({
  label: AggregateFunctionLabels[fn] ?? fn,
  value: fn,
}));

type ElementOption = { id: string; name: string; type: string };

const flattenElements = (nodes: CourseTreeNode[] | undefined): ElementOption[] => {
  const out: ElementOption[] = [];
  const walk = (arr: CourseTreeNode[] | undefined) => {
    (arr || []).forEach((n) => {
      if (n.data?.id) {
        out.push({ id: n.data.id, name: n.data.name, type: (n.data.type || '').toLowerCase() });
      }
      if (n.children?.length) walk(n.children as any);
    });
  };
  walk(nodes);
  return out;
};

const elementOptions = computed(() => flattenElements(props.treeData));
const gradableElementOptions = computed(() =>
  elementOptions.value.filter((el) => GRADABLE_ELEMENT_TYPES.has(el.type)),
);

/** Для completion/viewed допустимы атомарные элементы (лекции/тесты/практики/задания).
 *  На курс/модуль завершение навешивать семантически бессмысленно: у них нет
 *  собственного has_status — только агрегация потомков. */
const PROGRESSABLE_TYPES = new Set(['lecture', 'test', 'practice', 'assignment']);
const progressableElementOptions = computed(() =>
  elementOptions.value.filter((el) => PROGRESSABLE_TYPES.has(el.type)),
);

const elementOptionsFor = (rt: RuleType) => {
  if (rt === RuleType.GRADE_REQUIRED) return gradableElementOptions.value;
  if (rt === RuleType.COMPLETION_REQUIRED || rt === RuleType.VIEWED_REQUIRED)
    return progressableElementOptions.value;
  return elementOptions.value;
};

const addChild = () => children.value.push(newChild());
const removeChild = (key: number) => {
  if (children.value.length <= 2) return;
  children.value = children.value.filter((c) => c._key !== key);
};
const resetTypeSpecific = (c: ChildDraft) => {
  c.target_element_id = null;
  c.target_competency_id = null;
  c.passing_threshold = null;
  c.valid_from = null;
  c.valid_until = null;
  c.restricted_to_group_id = null;
  c.aggregate_function = null;
  c.aggregate_element_ids = null;
};

const isChildValid = (c: ChildDraft): boolean => {
  switch (c.rule_type) {
    case RuleType.COMPLETION_REQUIRED:
    case RuleType.VIEWED_REQUIRED:
      return !!c.target_element_id;
    case RuleType.GRADE_REQUIRED:
      return !!c.target_element_id && c.passing_threshold != null;
    case RuleType.COMPETENCY_REQUIRED:
      return !!c.target_competency_id;
    case RuleType.DATE_RESTRICTED:
      return !!c.valid_from && !!c.valid_until && c.valid_from.getTime() < c.valid_until.getTime();
    case RuleType.GROUP_RESTRICTED:
      return !!c.restricted_to_group_id;
    case RuleType.AGGREGATE_REQUIRED:
      return !!c.aggregate_function
        && Array.isArray(c.aggregate_element_ids)
        && c.aggregate_element_ids.length >= 1
        && c.passing_threshold != null;
    default:
      return false;
  }
};

const isFormValid = computed(() =>
  children.value.length >= 2 && children.value.every(isChildValid),
);

const childHint = (c: ChildDraft): string => {
  switch (c.rule_type) {
    case RuleType.COMPLETION_REQUIRED:
    case RuleType.VIEWED_REQUIRED:
      return c.target_element_id ? '' : 'выберите элемент';
    case RuleType.GRADE_REQUIRED:
      if (!c.target_element_id) return 'выберите тест/практику';
      if (c.passing_threshold == null) return 'задайте балл';
      return '';
    case RuleType.COMPETENCY_REQUIRED:
      return c.target_competency_id ? '' : 'выберите компетенцию';
    case RuleType.DATE_RESTRICTED:
      if (!c.valid_from || !c.valid_until) return 'задайте даты';
      if (c.valid_from.getTime() >= c.valid_until.getTime()) return 'начало раньше конца';
      return '';
    case RuleType.GROUP_RESTRICTED:
      return c.restricted_to_group_id ? '' : 'выберите группу';
    case RuleType.AGGREGATE_REQUIRED:
      if (!c.aggregate_function) return 'выберите функцию';
      if (!c.aggregate_element_ids?.length) return 'выберите элементы';
      if (c.passing_threshold == null) return 'задайте порог';
      return '';
    default:
      return 'заполните поля';
  }
};

const validationHint = computed<string>(() => {
  for (let i = 0; i < children.value.length; i++) {
    const h = childHint(children.value[i]);
    if (h) return `Условие ${i + 1}: ${h}`;
  }
  return '';
});

const toPolicyCreate = (c: ChildDraft): PolicyCreate => ({
  rule_type: c.rule_type,
  target_element_id: c.target_element_id ?? null,
  target_competency_id: c.target_competency_id ?? null,
  passing_threshold: c.passing_threshold ?? null,
  valid_from: c.valid_from ? c.valid_from.toISOString() : null,
  valid_until: c.valid_until ? c.valid_until.toISOString() : null,
  restricted_to_group_id: c.restricted_to_group_id ?? null,
  aggregate_function: c.aggregate_function ?? null,
  aggregate_element_ids: c.aggregate_element_ids ?? null,
  author_id: 'methodologist_smirnov',
  is_active: true,
});

const submit = async () => {
  if (!isFormValid.value) return;
  isSaving.value = true;
  try {
    const payload: PolicyCreate = {
      rule_type: RuleType.AND_COMBINATION,
      source_element_id: props.targetNode?.data?.id,
      author_id: 'methodologist_smirnov',
      is_active: true,
      nested_subpolicies: children.value.map(toPolicyCreate),
    } as PolicyCreate;
    await createPolicy(payload);
    toastService.showSuccess('Составное правило создано');
    emit('saved');
  } catch (err: any) {
    toastService.showError(err?.response?.data?.detail || 'Не удалось создать правило');
  } finally {
    isSaving.value = false;
  }
};
</script>

<template>
  <Card class="border border-surface-200 shadow-none overflow-hidden">
    <template #content>
      <div class="flex flex-col gap-5">
        <div class="flex justify-between items-center border-b border-surface-100 pb-3">
          <span class="font-bold text-xs text-surface-600 uppercase tracking-widest flex items-center gap-2">
            <i class="pi pi-sitemap"></i>
            Составное условие (И)
          </span>
           <p class="text-xs text-surface-500">Все условия ниже должны быть выполнены</p>
          <Button icon="pi pi-times" text rounded size="small" @click="$emit('cancelled')" />
        </div>

        <template v-for="(child, idx) in children" :key="child._key">
          <div
            v-if="idx > 0"
            class="flex items-center gap-3 text-xs font-bold text-surface-400 uppercase tracking-widest"
          >
            <div class="flex-1 h-px bg-surface-200"></div>
            <span>и</span>
            <div class="flex-1 h-px bg-surface-200"></div>
          </div>
          <div
            class="rounded-lg border border-surface-200 bg-surface-50 p-3 flex flex-col gap-3"
          >
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold text-surface-500 uppercase">Условие {{ idx + 1 }}</span>
            <Button
              v-if="children.length > 2"
              icon="pi pi-trash"
              text
              rounded
              size="small"
              severity="danger"
              @click="removeChild(child._key)"
            />
          </div>

          <div class="grid grid-cols-3 gap-4">
            <div class="flex flex-col gap-1">
              <label class="text-[11px] font-bold text-surface-500 uppercase">Тип</label>
              <Select
                v-model="child.rule_type"
                :options="atomicRuleTypeOptions"
                optionLabel="label"
                optionValue="value"
                class="w-full"
                @change="resetTypeSpecific(child)"
              />
            </div>

            <div
              v-if="[RuleType.COMPLETION_REQUIRED, RuleType.VIEWED_REQUIRED, RuleType.GRADE_REQUIRED].includes(child.rule_type)"
              class="flex flex-col gap-1 col-span-2"
            >
              <label class="text-[11px] font-bold text-surface-500 uppercase">Целевой элемент</label>
              <Select
                v-model="child.target_element_id"
                :options="elementOptionsFor(child.rule_type)"
                optionLabel="name"
                optionValue="id"
                :placeholder="child.rule_type === RuleType.GRADE_REQUIRED ? 'Тест/практика/задание' : 'Выберите элемент'"
                filter
                class="w-full"
              />
            </div>

            <div v-if="child.rule_type === RuleType.GRADE_REQUIRED" class="flex flex-col gap-1">
              <label class="text-[11px] font-bold text-surface-500 uppercase">Мин. балл</label>
              <InputNumber v-model="child.passing_threshold" :min="0" :max="100" class="w-full" />
            </div>

            <div v-if="child.rule_type === RuleType.COMPETENCY_REQUIRED" class="flex flex-col gap-1 col-span-2">
              <label class="text-[11px] font-bold text-surface-500 uppercase">Компетенция</label>
              <Select
                v-model="child.target_competency_id"
                :options="store.competencies"
                optionLabel="name"
                optionValue="id"
                placeholder="Выберите..."
                class="w-full"
              />
            </div>

            <div v-if="child.rule_type === RuleType.DATE_RESTRICTED" class="flex flex-col gap-1 col-span-2">
              <label class="text-[11px] font-bold text-surface-500 uppercase">Даты</label>
              <div class="grid grid-cols-2 gap-2">
                <DatePicker v-model="child.valid_from" showTime manualInput dateFormat="dd.mm.yy" class="w-full" placeholder="с" />
                <DatePicker
                  v-model="child.valid_until"
                  showTime manualInput dateFormat="dd.mm.yy"
                  :minDate="child.valid_from || undefined"
                  class="w-full" placeholder="по"
                />
              </div>
            </div>

            <div v-if="child.rule_type === RuleType.GROUP_RESTRICTED" class="flex flex-col gap-1 col-span-2">
              <label class="text-[11px] font-bold text-surface-500 uppercase">Группа</label>
              <Select
                v-model="child.restricted_to_group_id"
                :options="store.groups"
                optionLabel="name"
                optionValue="id"
                placeholder="Выберите группу"
                class="w-full"
              />
            </div>

            <template v-if="child.rule_type === RuleType.AGGREGATE_REQUIRED">
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Функция</label>
                <Select
                  v-model="child.aggregate_function"
                  :options="aggregateFunctionOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Порог</label>
                <InputNumber v-model="child.passing_threshold" :min="0" :max="100" class="w-full" />
              </div>
              <div class="flex flex-col gap-1 col-span-3">
                <label class="text-[11px] font-bold text-surface-500 uppercase">Элементы с оценками</label>
                <MultiSelect
                  v-model="child.aggregate_element_ids"
                  :options="gradableElementOptions"
                  optionLabel="name"
                  optionValue="id"
                  placeholder="Выберите тесты/практики"
                  filter
                  display="chip"
                  class="w-full"
                />
              </div>
            </template>
          </div>
          </div>
        </template>

        <Button
          v-if="children.length < 5"
          label="Добавить ещё условие"
          icon="pi pi-plus"
          severity="secondary"
          variant="text"
          class="self-start"
          @click="addChild"
        />

        <div class="flex justify-end items-center gap-4 pt-2 border-t border-surface-100">
          <span v-if="validationHint" class="text-xs text-surface-500 italic">
            <i class="pi pi-info-circle mr-1"></i>{{ validationHint }}
          </span>
          <Button label="Отмена" severity="secondary" variant="text" size="small" @click="$emit('cancelled')" />
          <Button
            label="Создать составное правило"
            icon="pi pi-check"
            size="small"
            :loading="isSaving"
            :disabled="!isFormValid"
            @click="submit"
          />
        </div>
      </div>
    </template>
  </Card>
</template>
