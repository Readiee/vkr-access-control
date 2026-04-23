<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useOntologyStore } from '@/stores/ontology';
import { getVerificationReport } from '@/api';
import type { PropertyReport } from '@/types';
import { VerificationPropertyStatus } from '@/types';

const store = useOntologyStore();
const isLoading = ref(false);

const PROPERTY_TITLES: Record<string, string> = {
  consistency: 'Непротиворечивость правил',
  acyclicity: 'Отсутствие циклических зависимостей',
  reachability: 'Достижимость элементов',
  redundancy: 'Избыточные правила',
  subsumption: 'Поглощённые правила',
};

const PROPERTY_HINTS: Record<string, string> = {
  consistency: 'Ни одно правило не противоречит структуре онтологии.',
  acyclicity: 'Между элементами нет круговых зависимостей доступа.',
  reachability: 'Каждый элемент может быть открыт хотя бы одним студентом.',
  redundancy: 'Нет правил, у которых условие строго слабее другого на том же элементе.',
  subsumption: 'Нет правил, доступных более узкой аудитории, чем уже разрешённые.',
};

const stored = computed(() => store.verificationForCurrentCourse);
const report = computed(() => stored.value?.report ?? null);
const isStale = computed(() => store.verificationStale);

const orderedEntries = computed<[string, PropertyReport][]>(() => {
  const rep = report.value;
  if (!rep) return [];
  const order = ['consistency', 'acyclicity', 'reachability', 'redundancy', 'subsumption'];
  return order
    .filter((k) => rep.properties[k])
    .map((k) => [k, rep.properties[k]] as [string, PropertyReport]);
});

const passedCount = computed(() =>
  orderedEntries.value.filter(([, p]) => p.status === VerificationPropertyStatus.PASSED).length,
);
const totalCount = computed(() => orderedEntries.value.length);
const failedCount = computed(() =>
  orderedEntries.value.filter(([, p]) => p.status === VerificationPropertyStatus.FAILED).length,
);

/** По умолчанию раскрываем только свойства с нарушениями или неопределённые —
 *  passed остаются свёрнутыми, методист сразу видит что требует внимания. */
const expandedKeys = computed<string[]>(() =>
  orderedEntries.value
    .filter(([, p]) => p.status !== VerificationPropertyStatus.PASSED)
    .map(([k]) => k),
);

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

const savedAtLabel = computed(() => {
  const ts = stored.value?.savedAt;
  if (!ts) return '';
  return new Date(ts).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
});

const runVerification = async () => {
  if (!store.currentCourseId) return;
  isLoading.value = true;
  try {
    // Сервер кэширует результат, если ABox не менялся с прошлой проверки —
    // full=true запрашивает все 5 свойств сразу.
    const result = await getVerificationReport(store.currentCourseId, true);
    store.saveVerification(store.currentCourseId, result);
  } finally {
    isLoading.value = false;
  }
};

onMounted(async () => {
  await store.fetchMeta();
});
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
        <Button
          icon="pi pi-play"
          :label="report ? 'Перезапустить' : 'Запустить проверку'"
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

    <div
      v-else-if="!report"
      class="bg-white p-12 text-center text-surface-500 rounded-xl shadow-sm border border-surface-100"
    >
      <i class="pi pi-shield text-4xl text-surface-300 mb-3"></i>
      <p class="mb-4">Отчёт по этому курсу ещё не построен.</p>
    </div>

    <div v-else class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div class="p-5 flex flex-wrap items-start justify-between gap-3 border-b border-surface-100">
        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-lg font-bold text-surface-800">
              {{ passedCount }} из {{ totalCount }} свойств выполнены
            </span>
            <Tag
              v-if="failedCount > 0"
              severity="danger"
              :value="`${failedCount} ${failedCount === 1 ? 'нарушение' : 'нарушений'}`"
            />
            <Tag
              v-if="report.partial"
              severity="warn"
              value="частичная проверка"
            />
            <Tag
              v-if="isStale"
              severity="warn"
              icon="pi pi-exclamation-triangle"
              value="Устарел - политики изменились"
            />
          </div>
          <span class="text-sm text-surface-500">
            {{ report.summary }}
            <span v-if="savedAtLabel" class="ml-2 text-surface-400">· проверка от {{ savedAtLabel }}</span>
          </span>
        </div>
      </div>

      <Accordion :multiple="true" :value="expandedKeys" class="border-none">
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
                найдено: {{ prop.violations.length }}
              </span>
            </span>
          </AccordionHeader>
          <AccordionContent>
            <p class="text-xs text-surface-500 mb-2">{{ PROPERTY_HINTS[key] }}</p>
            <p v-if="prop.status === VerificationPropertyStatus.PASSED" class="text-surface-600 py-2">
              Свойство выполнено, нарушений не найдено.
            </p>
            <p v-else-if="prop.status === VerificationPropertyStatus.UNKNOWN" class="text-surface-500 py-2 italic">
              Не удалось проверить автоматически (превышен лимит времени или недостаточно данных).
            </p>
            <div v-else class="flex flex-col gap-2">
              <div
                v-for="(v, idx) in prop.violations || []"
                :key="idx"
                class="rounded-lg border border-red-100 bg-red-50 p-3 text-sm"
              >
                <div v-if="v.message" class="text-surface-700">{{ v.message }}</div>
                <div v-if="v.path" class="text-surface-700">
                  Цикл: <span class="font-medium">{{ (v.path_names?.length ? v.path_names : v.path).join(' → ') }}</span>
                </div>
                <div v-if="v.policy_names?.length" class="text-surface-700 text-xs mt-1">
                  Участвующие правила: {{ v.policy_names.join(', ') }}
                </div>
                <div v-if="v.element_id && !v.dominant" class="text-surface-700">
                  Элемент: <span class="font-medium">{{ v.element_name || v.element_id }}</span>
                  <span v-if="v.reason"> — {{ v.reason }}</span>
                </div>
                <div v-if="v.policy_id && !v.dominant" class="text-surface-700">
                  Правило: <span class="font-medium">{{ v.policy_name || v.policy_id }}</span>
                  <span v-if="v.reason"> — {{ v.reason }}</span>
                </div>
                <div v-if="v.dominant && v.dominated" class="text-surface-700">
                  «<span class="font-medium">{{ v.dominant_name || v.dominant }}</span>» поглощает
                  «<span class="font-medium">{{ v.dominated_name || v.dominated }}</span>»
                  <span v-if="v.element"> на элементе «{{ v.element_name || v.element }}»</span>
                  <span v-if="v.witness" class="text-xs text-surface-500">; {{ v.witness }}</span>
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
    </div>
  </div>
</template>
