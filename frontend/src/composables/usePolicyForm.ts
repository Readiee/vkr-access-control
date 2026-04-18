import { ref, watch, computed } from 'vue';
import { RuleType, type PolicyCreate } from '@/types';

interface PolicyFormState extends Omit<PolicyCreate, 'available_from' | 'available_until'> {
  available_from: Date | null;
  available_until: Date | null;
}

export function usePolicyForm(props: any, emit: any) {
  const defaultForm = (): PolicyFormState => ({
    source_element_id: props.targetNode?.id ?? '',
    rule_type: RuleType.COMPLETION_REQUIRED,
    author_id: 'methodist_1', // TODO: заменить заглушку когда появится авторизация
    target_element_id: null,
    target_competency_id: null,
    passing_threshold: null,
    available_from: null,
    available_until: null,
    is_active: true,
  });

  const form = ref<PolicyFormState>(defaultForm());

  const treeSelectModel = computed({
    get: () => {
      const targetId = form.value.target_element_id;
      return targetId ? { [targetId]: true } : null;
    },
    set: (val: any) => {
      if (val && typeof val === 'object') {
        const keys = Object.keys(val);
        // Сеттер сразу сохраняет чистую строку в form.value
        form.value.target_element_id = keys.length ? keys[0] : null;
      } else {
        form.value.target_element_id = null;
      }
    },
  });

  const resetForm = () => {
    if (props.initialData) {
      form.value = {
        source_element_id: props.initialData.source_element_id || props.targetNode?.data?.id || '',
        rule_type: props.initialData.rule_type,
        author_id: props.initialData.author_id || 'methodist_1',
        target_element_id: props.initialData.target_element_id ?? null,
        target_competency_id: props.initialData.target_competency_id ?? props.initialData.competency_id ?? null,
        passing_threshold: props.initialData.passing_threshold ?? null,
        available_from: props.initialData.available_from ? new Date(props.initialData.available_from) : null,
        available_until: props.initialData.available_until ? new Date(props.initialData.available_until) : null,
        is_active: props.initialData.is_active ?? true,
      };
    } else {
      form.value = { ...defaultForm(), source_element_id: props.targetNode?.data?.id || '' };
    }
  };

  watch(() => props.initialData, () => resetForm(), { immediate: true });

  watch(() => form.value.rule_type, () => {
    form.value.target_element_id = null;
  });

  const submitForm = () => {
    const payload: PolicyCreate = {
      ...form.value,
      available_from: form.value.available_from ? form.value.available_from.toISOString() : null,
      available_until: form.value.available_until ? form.value.available_until.toISOString() : null,
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
