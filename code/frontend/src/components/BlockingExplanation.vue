<script setup lang="ts">
import { ref, watch } from 'vue';
import { getBlockingExplanation } from '@/api';
import type { BlockingExplanation } from '@/types';
import { RuleTypeMap } from '@/utils/formatters';

const props = defineProps<{
  studentId: string | null;
  elementId: string | null;
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void;
}>();

const report = ref<BlockingExplanation | null>(null);
const isLoading = ref(false);
const errorMsg = ref<string | null>(null);

const localVisible = ref(props.visible);

watch(() => props.visible, (v) => {
  localVisible.value = v;
  if (v) fetchReport();
});

watch(() => localVisible.value, (v) => emit('update:visible', v));

const fetchReport = async () => {
  if (!props.studentId || !props.elementId) return;
  isLoading.value = true;
  errorMsg.value = null;
  report.value = null;
  try {
    report.value = await getBlockingExplanation(props.studentId, props.elementId);
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail ?? 'Не удалось получить объяснение';
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <Dialog
    v-model:visible="localVisible"
    modal
    :style="{ width: '560px' }"
    header="Объяснение доступа"
  >
    <div v-if="isLoading" class="py-8 text-center text-surface-500">
      <i class="pi pi-spin pi-spinner text-3xl text-primary-400 mb-2"></i>
      <p>Запрашиваем отчёт...</p>
    </div>

    <div v-else-if="errorMsg" class="py-6 text-center text-red-500 text-sm">
      {{ errorMsg }}
    </div>

    <div v-else-if="report" class="flex flex-col gap-4">
      <div class="flex items-center gap-3">
        <Tag
          :severity="report.is_available ? 'success' : 'danger'"
          :value="report.is_available ? 'Доступен' : 'Заблокирован'"
        />
        <span class="text-sm text-surface-700">
          <code>{{ report.element_id }}</code>
        </span>
      </div>

      <div
        v-if="report.cascade_blocker"
        class="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm"
      >
        <div class="font-semibold text-orange-700 mb-1">
          Каскадная блокировка
        </div>
        <div class="text-surface-700">
          Родительский элемент <code>{{ report.cascade_blocker }}</code> недоступен.
          <span v-if="report.cascade_reason"> {{ report.cascade_reason }}</span>
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <div class="text-xs font-semibold text-surface-500 uppercase tracking-wider">
          Применимые политики
        </div>
        <div
          v-for="p in report.applicable_policies"
          :key="p.policy_id"
          class="rounded-lg border p-3 text-sm"
          :class="p.satisfied ? 'border-green-100 bg-green-50' : 'border-red-100 bg-red-50'"
        >
          <div class="flex items-center gap-2 mb-1">
            <Tag
              :severity="p.satisfied ? 'success' : 'danger'"
              :value="p.satisfied ? 'Выполнено' : 'Не выполнено'"
            />
            <Tag
              :severity="RuleTypeMap[p.rule_type]?.severity || 'secondary'"
              :value="RuleTypeMap[p.rule_type]?.label || p.rule_type"
            />
            <code class="text-xs text-surface-500">{{ p.policy_id }}</code>
          </div>
          <div v-if="!p.satisfied && p.failure_reason" class="text-surface-700">
            {{ p.failure_reason }}
          </div>
          <pre
            v-if="!p.satisfied && p.witness && Object.keys(p.witness).length"
            class="mt-2 text-xs text-surface-600 bg-white/60 rounded p-2 overflow-x-auto"
          >{{ JSON.stringify(p.witness, null, 2) }}</pre>
        </div>
        <p
          v-if="!report.applicable_policies.length"
          class="text-surface-500 italic text-sm py-2"
        >
          На элементе нет активных политик — доступ открыт по умолчанию.
        </p>
      </div>

      <div v-if="report.justification" class="flex flex-col gap-2">
        <div class="text-xs font-semibold text-surface-500 uppercase tracking-wider">
          Трассировка вывода (SWRL body bindings)
        </div>
        <JustificationTreeView :node="report.justification" :depth="0" />
      </div>
    </div>

    <template #footer>
      <Button label="Закрыть" icon="pi pi-times" severity="secondary" @click="localVisible = false" />
    </template>
  </Dialog>
</template>
