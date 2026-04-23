import { computed, ref, watch } from 'vue';
import { AggregateFunction, RuleType, type PolicyCreate } from '@/types';
import { SANDBOX_AUTHOR_ID } from '@/utils/auth';

interface PolicyFormState extends Omit<PolicyCreate, 'valid_from' | 'valid_until'> {
  valid_from: Date | null;
  valid_until: Date | null;
}

export function usePolicyForm(props: any, emit: any) {
  const defaultForm = (): PolicyFormState => ({
    source_element_id: props.targetNode?.data?.id ?? null,
    rule_type: RuleType.COMPLETION_REQUIRED,
    author_id: SANDBOX_AUTHOR_ID,
    target_element_id: null,
    target_competency_id: null,
    passing_threshold: null,
    valid_from: null,
    valid_until: null,
    restricted_to_group_id: null,
    subpolicy_ids: null,
    aggregate_function: null,
    aggregate_element_ids: null,
    is_active: true,
  });

  const form = ref<PolicyFormState>(defaultForm());

  const treeSelectModel = computed({
    get: () => {
      const targetId = form.value.target_element_id;
      return targetId ? { [targetId]: true } : null;
    },
    set: (val: any) => {
      if (!val || typeof val !== 'object') {
        form.value.target_element_id = null;
        return;
      }
      // В single-mode PrimeVue отдаёт { id: true } или { id: { checked: true } }.
      // partialChecked у родителей в single-mode не используется, но фильтр
      // по явному checked-true защитит нас, если тип когда-нибудь расширят.
      const picked = Object.entries(val).find(
        ([, v]) => v === true || (v as any)?.checked === true,
      );
      form.value.target_element_id = picked ? picked[0] : null;
    },
  });

  const resetForm = () => {
    if (props.initialData) {
      const d = props.initialData;
      form.value = {
        source_element_id: d.source_element_id || props.targetNode?.data?.id || null,
        rule_type: d.rule_type,
        author_id: d.author_id || SANDBOX_AUTHOR_ID,
        target_element_id: d.target_element_id ?? null,
        // course_service сериализует поле как competency_id, policy_service — как target_competency_id
        target_competency_id: d.target_competency_id ?? d.competency_id ?? null,
        passing_threshold: d.passing_threshold ?? null,
        valid_from: d.valid_from ? new Date(d.valid_from) : null,
        valid_until: d.valid_until ? new Date(d.valid_until) : null,
        restricted_to_group_id: d.restricted_to_group_id ?? null,
        subpolicy_ids: d.subpolicy_ids ?? null,
        aggregate_function: d.aggregate_function ?? null,
        aggregate_element_ids: d.aggregate_element_ids ?? null,
        is_active: d.is_active ?? true,
      };
    } else {
      form.value = { ...defaultForm(), source_element_id: props.targetNode?.data?.id || null };
    }
  };

  watch(() => props.initialData, () => resetForm(), { immediate: true });

  // При смене типа правила очищаем несовместимые поля, чтобы не слать их на бэкенд
  watch(() => form.value.rule_type, (rt) => {
    form.value.target_element_id = null;
    form.value.target_competency_id = null;
    form.value.passing_threshold = null;
    form.value.valid_from = null;
    form.value.valid_until = null;
    form.value.restricted_to_group_id = null;
    form.value.subpolicy_ids = null;
    form.value.aggregate_function = null;
    form.value.aggregate_element_ids = null;

    if (rt === RuleType.AGGREGATE_REQUIRED) {
      form.value.aggregate_function = AggregateFunction.AVG;
    }
  });

  const submitForm = () => {
    const payload: PolicyCreate = {
      ...form.value,
      valid_from: form.value.valid_from ? form.value.valid_from.toISOString() : null,
      valid_until: form.value.valid_until ? form.value.valid_until.toISOString() : null,
    } as unknown as PolicyCreate;

    emit('submit', payload);
  };

  const handleDelete = () => {
    if (props.initialData?.id) emit('delete', props.initialData.id);
  };

  return {
    form,
    treeSelectModel,
    submitForm,
    handleDelete,
    resetForm,
  };
}
