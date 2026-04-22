<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useOntologyStore } from '@/stores/ontology';
import { getVerificationReport } from '@/api';
import type { PropertyReport, VerificationReport } from '@/types';
import { VerificationPropertyStatus } from '@/types';

const store = useOntologyStore();
const report = ref<VerificationReport | null>(null);
const isLoading = ref(false);
const includeFull = ref(false);

const PROPERTY_TITLES: Record<string, string> = {
  consistency: 'СВ-1. Непротиворечивость',
  acyclicity: 'СВ-2. Отсутствие циклов',
  reachability: 'СВ-3. Достижимость',
  redundancy: 'СВ-4. Избыточные правила',
  subsumption: 'СВ-5. Поглощённые правила',
};

const orderedEntries = computed<[string, PropertyReport][]>(() => {
  if (!report.value) return [];
  const order = ['consistency', 'acyclicity', 'reachability', 'redundancy', 'subsumption'];
  return order
    .filter((k) => report.value!.properties[k])
    .map((k) => [k, report.value!.properties[k]] as [string, PropertyReport]);
});

const statusSeverity = (status: string): string => {
  if (status === VerificationPropertyStatus.PASSED) return 'success';
  if (status === VerificationPropertyStatus.FAILED) return 'danger';
  return 'warn';
};

const statusLabel = (status: string): string => {
  if (status === VerificationPropertyStatus.PASSED) return 'Выполнено';
  if (status === VerificationPropertyStatus.FAILED) return 'Нарушение';
  return 'Не определено';
};

const runVerification = async () => {
  if (!store.currentCourseId) return;
  isLoading.value = true;
  try {
    report.value = await getVerificationReport(store.currentCourseId, includeFull.value);
  } finally {
    isLoading.value = false;
  }
};

onMounted(async () => {
  await store.fetchMeta();
});

watch(() => store.currentCourseId, (id) => {
  report.value = null;
  if (id) runVerification();
}, { immediate: true });
</script>

<template>
  <div class="flex flex-col gap-4 max-w-6xl mx-auto">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap justify-between items-center gap-4">
      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Выбор курса</label>
        <Select
          v-model="store.currentCourseId"
          :options="store.courses"
          optionLabel="name"
          optionValue="id"
          placeholder="Выберите курс"
          emptyMessage="Нет курсов"
          filter
          class="w-96"
        />
      </div>
      <div class="flex items-center gap-3">
        <ToggleSwitch v-model="includeFull" input-id="full-toggle" />
        <label for="full-toggle" class="text-sm text-surface-700">
          Расширенная (СВ-4/5)
        </label>
        <Button
          icon="pi pi-refresh"
          label="Перезапустить"
          :loading="isLoading"
          :disabled="!store.currentCourseId"
          @click="runVerification"
          severity="primary"
        />
      </div>
    </div>

    <div
      v-if="!store.currentCourseId"
      class="bg-white p-12 text-center text-surface-500 rounded-xl shadow-sm border border-surface-100"
    >
      <i class="pi pi-search text-4xl text-surface-300 mb-3"></i>
      <p>Выберите курс для запуска верификации</p>
    </div>

    <div
      v-else-if="isLoading && !report"
      class="bg-white p-12 text-center text-surface-500 rounded-xl shadow-sm border border-surface-100"
    >
      <i class="pi pi-spin pi-spinner text-4xl text-primary-400 mb-3"></i>
      <p>Идёт верификация...</p>
    </div>

    <template v-else-if="report">
      <div
        class="bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex flex-wrap items-center justify-between gap-3"
      >
        <div class="flex flex-col gap-1">
          <span class="text-xs font-semibold text-surface-400 uppercase tracking-wider">Отчёт</span>
          <span class="text-sm text-surface-700">
            run_id: <code class="text-surface-500">{{ report.run_id.slice(0, 12) }}…</code>
          </span>
          <span class="text-xs text-surface-500">
            {{ report.summary }} · {{ report.duration_ms }} мс
            <Tag
              v-if="report.partial"
              severity="warn"
              value="partial"
              class="ml-2"
            />
          </span>
        </div>
        <div class="flex gap-2">
          <Tag
            v-for="[key, prop] in orderedEntries"
            :key="key"
            :severity="statusSeverity(prop.status)"
            :value="PROPERTY_TITLES[key].split('. ')[0]"
          />
        </div>
      </div>

      <Accordion :multiple="true" :value="orderedEntries.map(([k]) => k)">
        <AccordionPanel
          v-for="[key, prop] in orderedEntries"
          :key="key"
          :value="key"
        >
          <AccordionHeader>
            <span class="flex items-center gap-3">
              <Tag :severity="statusSeverity(prop.status)" :value="statusLabel(prop.status)" />
              <span class="font-semibold">{{ PROPERTY_TITLES[key] }}</span>
              <span v-if="prop.violations?.length" class="text-sm text-surface-500">
                нарушений: {{ prop.violations.length }}
              </span>
            </span>
          </AccordionHeader>
          <AccordionContent>
            <p v-if="prop.status === VerificationPropertyStatus.PASSED" class="text-surface-600 py-2">
              Свойство выполнено, нарушений не найдено.
            </p>
            <p v-else-if="prop.status === VerificationPropertyStatus.UNKNOWN" class="text-surface-500 py-2 italic">
              Свойство не могло быть проверено (reasoning не завершился или не применимо).
            </p>
            <div v-else class="flex flex-col gap-2">
              <div
                v-for="(v, idx) in prop.violations || []"
                :key="idx"
                class="rounded-lg border border-red-100 bg-red-50 p-3 text-sm"
              >
                <div class="flex items-center gap-2 mb-1">
                  <Tag severity="danger" :value="v.code" />
                </div>
                <div v-if="v.message" class="text-surface-700">{{ v.message }}</div>
                <div v-if="v.path" class="text-surface-700">
                  Цикл: <code>{{ v.path.join(' → ') }}</code>
                </div>
                <div v-if="v.element_id" class="text-surface-700">
                  Элемент: <code>{{ v.element_id }}</code>
                  <span v-if="v.reason"> — {{ v.reason }}</span>
                </div>
                <div v-if="v.policy_id" class="text-surface-700">
                  Политика: <code>{{ v.policy_id }}</code>
                  <span v-if="v.reason"> — {{ v.reason }}</span>
                </div>
                <div v-if="v.dominant && v.dominated" class="text-surface-700">
                  <code>{{ v.dominant }}</code> поглощает <code>{{ v.dominated }}</code>
                  <span v-if="v.element"> на элементе <code>{{ v.element }}</code></span>
                  <span v-if="v.witness">; {{ v.witness }}</span>
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
    </template>
  </div>
</template>
