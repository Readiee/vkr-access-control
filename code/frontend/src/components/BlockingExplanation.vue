<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { getBlockingExplanation } from '@/api';
import type { BlockingExplanation } from '@/types';
import { RuleTypeMap } from '@/utils/formatters';

const showTrace = ref(false);

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

const localVisible = computed<boolean>({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
});

watch(() => props.visible, (v) => {
  if (v) {
    showTrace.value = false;
    fetchReport();
  }
});

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
        <span class="text-sm font-medium text-surface-800">
          {{ report.element_name || report.element_id }}
        </span>
      </div>

      <div
        v-if="report.cascade_blocker"
        class="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm"
      >
        <div class="font-semibold text-orange-700 mb-1">
          Заблокировано через родительский элемент
        </div>
        <div class="text-surface-700">
          «{{ report.cascade_blocker_name || report.cascade_blocker }}» недоступен студенту.
          <span v-if="report.cascade_reason"> {{ report.cascade_reason }}</span>
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <div class="text-xs font-semibold text-surface-500 uppercase tracking-wider">
          Применимые правила
        </div>
        <div
          v-for="p in report.applicable_policies"
          :key="p.policy_id"
          class="rounded-lg border p-3 text-sm"
          :class="p.satisfied ? 'border-green-100 bg-green-50' : 'border-red-100 bg-red-50'"
        >
          <div class="flex items-center gap-2 mb-1 flex-wrap">
            <Tag
              :severity="p.satisfied ? 'success' : 'danger'"
              :value="p.satisfied ? 'Выполнено' : 'Не выполнено'"
            />
            <Tag
              :severity="RuleTypeMap[p.rule_type]?.severity || 'secondary'"
              :value="RuleTypeMap[p.rule_type]?.label || p.rule_type"
            />
            <span class="text-sm text-surface-800 font-medium">
              {{ p.policy_name || p.policy_id }}
            </span>
          </div>
          <div v-if="!p.satisfied && p.failure_reason" class="text-surface-700">
            {{ p.failure_reason }}
          </div>
          <ul
            v-if="!p.satisfied && p.witness?.subpolicies?.length"
            class="mt-2 ml-2 list-disc list-inside text-surface-700 text-xs space-y-0.5"
          >
            <li v-for="(sub, i) in p.witness.subpolicies" :key="i">
              <span :class="sub.satisfied ? 'text-green-700' : 'text-red-700'">
                {{ sub.satisfied ? '✓' : '✗' }}
              </span>
              <span class="font-medium">{{ sub.name || sub.id }}</span>
              <span v-if="!sub.satisfied && sub.failure_reason" class="text-surface-500">
                — {{ sub.failure_reason }}
              </span>
            </li>
          </ul>
        </div>
        <p
          v-if="!report.applicable_policies.length"
          class="text-surface-500 italic text-sm py-2"
        >
          На элементе нет активных правил — доступ открыт по умолчанию.
        </p>
      </div>

      <div v-if="report.justification" class="flex flex-col gap-2 pt-2 border-t border-surface-100">
        <Button
          :icon="showTrace ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
          :label="showTrace ? 'Скрыть техническое объяснение' : 'Показать техническое объяснение'"
          severity="secondary"
          variant="text"
          size="small"
          class="self-start !px-0"
          @click="showTrace = !showTrace"
        />
        <div v-if="showTrace" class="flex flex-col gap-2">
          <p class="text-xs text-surface-500">
            Полная трассировка вывода резонера: какие факты из онтологии удовлетворили
            условия правила (или наоборот не дали вывести доступ). Для разработчиков и аудита.
          </p>
          <JustificationTreeView :node="report.justification" :depth="0" />
        </div>
      </div>
    </div>

    <template #footer>
      <Button label="Закрыть" icon="pi pi-times" severity="secondary" @click="localVisible = false" />
    </template>
  </Dialog>
</template>
