<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ElementTypeMap, buildCompetencyTree } from '@/utils/formatters';
import { useOntologyStore } from '@/stores/ontology';
import { setElementCompetencies } from '@/api';
import { toastService } from '@/utils/toastService';
import PolicyRuleCard from './PolicyRuleCard.vue';
import CompositePolicyEditor from './CompositePolicyEditor.vue';

const props = defineProps<{
  targetNode: any;
  treeData: any[];
}>();

const store = useOntologyStore();

// Стейт для новых несохраненных правил
const newPolicies = ref<any[]>([]);
const compositeDraftOpen = ref(false);

// Выдаваемые компетенции (assesses) — локальный map для TreeSelect.
const assessesMap = ref<Record<string, { checked: boolean; partialChecked: boolean }>>({});

const syncAssessesFromNode = () => {
  const ids: string[] = (props.targetNode?.data?.assesses ?? []).map((c: any) => c.id);
  const map: Record<string, { checked: boolean; partialChecked: boolean }> = {};
  ids.forEach((id) => {
    map[id] = { checked: true, partialChecked: false };
  });
  assessesMap.value = map;
};

const competencyTree = computed(() => buildCompetencyTree(store.competencies));

// id узла лежит в data, не на верхнем уровне CourseTreeNode
watch(
  () => props.targetNode?.data?.id,
  () => {
    newPolicies.value = [];
    compositeDraftOpen.value = false;
    syncAssessesFromNode();
  },
  { immediate: true },
);

const addNewPolicy = () => {
  // Добавляем пустую болванку в начало или конец (пусть будет в конец)
  newPolicies.value.push({
    _isNew: true,
    id: 'new-' + Date.now().toString(),
  });
};

const handleSaved = () => {
  newPolicies.value = [];
  compositeDraftOpen.value = false;
};

const saveAssesses = async () => {
  const selected = Object.keys(assessesMap.value).filter((k) => assessesMap.value[k]?.checked);
  const current = new Set((props.targetNode?.data?.assesses ?? []).map((c: any) => c.id));
  const changed =
    current.size !== selected.length || selected.some((id) => !current.has(id));
  if (!changed) return;

  try {
    const result = await setElementCompetencies(props.targetNode.data.id, selected);
    // Patch локально — чтобы не перезагружать дерево целиком.
    props.targetNode.data.assesses = result.assesses;
    toastService.showSuccess(
      selected.length
        ? `Элемент выдаёт ${selected.length} ${selected.length === 1 ? 'компетенцию' : 'компетенций'}`
        : 'Выдача компетенций снята',
    );
  } catch {
    syncAssessesFromNode();  // откат локального map — сервер не принял
  }
};
</script>

<template>
  <div class="flex flex-col gap-4 pb-8 max-w-[900px]">
    <!-- Header: Element Meta -->
    <div class="flex justify-between items-start border-b border-surface-100 pb-4">
      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-3">
          <Tag 
            :value="ElementTypeMap[targetNode.data.type as keyof typeof ElementTypeMap] || targetNode.data.type" 
            severity="secondary" 
            rounded 
            class="text-[10px] px-2 font-bold uppercase" 
          />
          <span class="text-xs text-surface-400">ID: {{ targetNode.data.id }}</span>
        </div>
        <h3 class="text-2xl font-bold text-surface-900 leading-tight tracking-tight">
          {{ targetNode.data.name }}
        </h3>
      </div>
      <Tag
        :value="targetNode.data.policies?.length ? 'С политиками' : 'Без политик'"
        severity="secondary"
        rounded
        class="text-[10px] whitespace-nowrap"
      />
    </div>

    <!-- Выдаваемые компетенции (SWRL H-2) -->
    <div class="flex flex-col gap-1 pb-4 border-b border-surface-100">
      <label class="text-[11px] font-bold text-surface-500 uppercase flex items-center gap-2">
        Выдаваемые компетенции
        <span class="text-[10px] text-surface-400 font-normal normal-case tracking-normal">
          — студент получит их при прохождении элемента
        </span>
      </label>
      <TreeSelect
        v-model="assessesMap"
        :options="competencyTree"
        selectionMode="checkbox"
        placeholder="Нет — элемент не выдаёт компетенций"
        emptyMessage="В онтологии нет компетенций"
        display="chip"
        filter
        class="w-full"
        @hide="saveAssesses"
      />
    </div>

    <!-- Policy List Header -->
    <div class="flex flex-col gap-2">
      <h3 class="text-lg font-bold text-surface-800 flex items-center gap-2 mb-2">
        Правила доступа
        <span 
          v-if="targetNode.data.policies?.length" 
          class="bg-surface-100 text-surface-500 text-xs px-2 py-0.5 rounded-full"
        >
          {{ targetNode.data.policies.length }}
        </span>
      </h3>
      
      <!-- Пустое состояние -->
      <div v-if="!targetNode.data.policies?.length && !newPolicies.length && !compositeDraftOpen" class="py-6 bg-surface-50 rounded-2xl border border-surface-200 flex flex-col items-center justify-center text-center px-4">
        <p class="text-surface-600 font-medium mb-1">Нет ограничений</p>
        <p class="text-surface-400 text-sm max-w-96">Для этого элемента нет правил доступа. Он доступен всем студентам по умолчанию.</p>
      </div>

      <div class="flex flex-col gap-2">
        <!-- Существующие политики: между карточками — неявный OR через мета-правило SWRL -->
        <template v-for="(policy, idx) in targetNode.data.policies" :key="policy.id">
          <div v-if="Number(idx) > 0" class="flex items-center gap-3 text-xs font-bold text-surface-400 uppercase tracking-widest">
            <div class="flex-1 h-px bg-surface-200"></div>
            <span>или</span>
            <div class="flex-1 h-px bg-surface-200"></div>
          </div>
          <PolicyRuleCard
            :initial-data="policy"
            :target-node="targetNode"
            :tree-data="treeData"
            :edit-mode="true"
            @saved="handleSaved"
          />
        </template>

        <!-- Новые (черновики) -->
        <template v-for="(newPol, idx) in newPolicies" :key="newPol.id">
          <div
            v-if="targetNode.data.policies?.length || Number(idx) > 0"
            class="flex items-center gap-3 text-xs font-bold text-surface-400 uppercase tracking-widest"
          >
            <div class="flex-1 h-px bg-surface-200"></div>
            <span>или</span>
            <div class="flex-1 h-px bg-surface-200"></div>
          </div>
          <PolicyRuleCard
            :target-node="targetNode"
            :tree-data="treeData"
            :edit-mode="false"
            @saved="handleSaved"
            @cancelled="newPolicies = newPolicies.filter(p => p.id !== newPol.id)"
          />
        </template>
      </div>

      <Card v-if="compositeDraftOpen" class="border border-surface-200 shadow-none overflow-hidden">
        <template #content>
          <CompositePolicyEditor
            :target-node="targetNode"
            :tree-data="treeData"
            @saved="handleSaved"
            @cancelled="compositeDraftOpen = false"
          />
        </template>
      </Card>

      <div class="grid grid-cols-2 gap-3">
        <Button
          v-if="newPolicies.length < 3"
          label="Добавить простое правило"
          icon="pi pi-plus"
          variant="outlined"
          class="border-dashed py-4 bg-white/50 hover:bg-white hover:border-primary-400 transition-colors"
          @click="addNewPolicy"
        />
        <Button
          v-if="!compositeDraftOpen"
          label="Составное условие (И)"
          icon="pi pi-plus"
          variant="outlined"
          severity="secondary"
          class="border-dashed py-4 bg-white/50 hover:bg-white hover:border-primary-400 transition-colors"
          @click="compositeDraftOpen = true"
        />
      </div>
    </div>
  </div>
</template>
