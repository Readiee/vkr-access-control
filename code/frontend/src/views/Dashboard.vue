<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useOntologyStore } from '@/stores/ontology';
import { useCourseTree } from '@/composables/useCourseTree';

import ConfirmDialog from 'primevue/confirmdialog';
import PolicyWorkspace from '@/components/PolicyWorkspace.vue';
import { formatPolicyBadgeText } from '@/utils/formatters';
import { RuleType } from '@/types';

const store = useOntologyStore();
const { selectedNode, selectedNodeKey, expandedKeys, onNodeSelect } = useCourseTree(() => store.currentCourseTree);

onMounted(async () => {
  await store.fetchMeta();
});

const loadTree = async () => {
  if (!store.currentCourseId) return;
  await store.fetchCourseTree(store.currentCourseId);
  // Сброс выбора при смене курса
  selectedNode.value = null;
  selectedNodeKey.value = {};
};

watch(() => store.currentCourseId, (newId) => {
  if (newId) loadTree();
}, { immediate: true });

</script>

<template>
  <div class="flex flex-col gap-4 max-w-6xl mx-auto">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap justify-between items-center gap-4 ">
      <div class="flex flex-col gap-1">
        <label class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Выбор курса</label>
        <Select 
          v-model="store.currentCourseId" 
          :options="store.courses"
          optionLabel="name" 
          optionValue="id"
          placeholder="Выберите курс" 
          emptyMessage="Нет доступных курсов"
          filter
          filterPlaceholder="Поиск курса..."
          class="w-96"
        />
      </div>
    </div>

    <!-- Основная область -->
    <div v-if="!store.currentCourseId" class="bg-white p-12 text-center text-surface-500 rounded-xl shadow-sm border border-surface-100 flex-1">
       <i class="pi pi-inbox text-4xl text-surface-300 mb-3"></i>
       <p>Выберите курс для загрузки структуры</p>
    </div>
    
    <div v-else class="grid grid-cols-5 md:grid-cols-5 gap-4 h-[calc(100vh-156px)]">
      <div class="col-span-2 bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex flex-col h-full overflow-hidden">
        <h3 class="text-lg font-bold mb-4 text-surface-800">Дерево курса</h3>
        
        <div class="overflow-y-auto flex-1 custom-scrollbar pr-2">
            <Tree 
              v-model:expandedKeys="expandedKeys"
              :value="store.currentCourseTree" 
              selectionMode="single" 
              v-model:selectionKeys="selectedNodeKey" 
              @nodeSelect="onNodeSelect"
              class="w-full border-none p-0"
              :loading="store.isLoading"
            >
              <template #default="slotProps">
                 <div class="flex items-center justify-between w-full py-1.5 overflow-hidden">
                   <span class="flex-1 min-w-0 w-full break-words leading-tight pr-2" :class="{'font-semibold text-surface-900': slotProps.node.data.type === 'module'}">
                     {{ slotProps.node.label || slotProps.node.data.name }}
                   </span>
                   
                   <div class="flex gap-1 shrink-0 ml-auto" v-if="slotProps.node.data.policies?.length">
                     <i v-for="pol in slotProps.node.data.policies" :key="pol.id"
                        class="pi text-sm p-1 text-surface-400 hover:text-primary-500 transition-colors cursor-help"
                        :class="{
                          'pi-check-circle': pol.rule_type === RuleType.COMPLETION_REQUIRED,
                          'pi-star': pol.rule_type === RuleType.GRADE_REQUIRED,
                          'pi-eye': pol.rule_type === RuleType.VIEWED_REQUIRED,
                          'pi-calendar': pol.rule_type === RuleType.DATE_RESTRICTED,
                          'pi-graduation-cap': pol.rule_type === RuleType.COMPETENCY_REQUIRED,
                          'pi-users': pol.rule_type === RuleType.GROUP_RESTRICTED,
                          'pi-sitemap': pol.rule_type === RuleType.AND_COMBINATION || pol.rule_type === RuleType.OR_COMBINATION,
                          'pi-percentage': pol.rule_type === RuleType.AGGREGATE_REQUIRED,
                          'opacity-40': pol.is_active === false
                        }"
                        v-tooltip.left="{ 
                          value: formatPolicyBadgeText(pol, store.currentCourseTree, store.competencies),
                          pt: { text: { style: 'max-width: 460px; font-size: 0.85rem; line-height: 1.4;' } } 
                        }"
                     ></i>
                   </div>
                 </div>
              </template>
            </Tree>
        </div>
      </div>

      <div class="col-span-3 bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col h-full overflow-y-auto custom-scrollbar">
        <PolicyWorkspace 
          v-if="selectedNode"
          :target-node="selectedNode"
          :tree-data="store.currentCourseTree"
        />
        <div v-else class="h-full flex flex-col items-center justify-center text-surface-400">
          <i class="pi pi-arrow-left text-4xl mb-4"></i>
          <p>Выберите элемент в дереве для настройки правил</p>
        </div>
      </div>
    </div>
    
    <ConfirmDialog></ConfirmDialog>
  </div>
</template>
