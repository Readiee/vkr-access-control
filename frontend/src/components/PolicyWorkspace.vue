<script setup lang="ts">
import { ref, watch } from 'vue';
import { ElementTypeMap } from '@/utils/formatters';
import PolicyRuleCard from './PolicyRuleCard.vue';

const props = defineProps<{
  targetNode: any;
  treeData: any[];
}>();

// Стейт для новых несохраненных правил
const newPolicies = ref<any[]>([]);

// Когда выбираем новый узел, обнуляем список новых полей
watch(() => props.targetNode?.id, () => {
  newPolicies.value = [];
});

const addNewPolicy = () => {
  // Добавляем пустую болванку в начало или конец (пусть будет в конец)
  newPolicies.value.push({ 
    _isNew: true, 
    id: 'new-' + Date.now().toString(),
  });
};

const handleSaved = () => {
  newPolicies.value = [];
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
      <div v-if="!targetNode.data.policies?.length && !newPolicies.length" class="py-6 bg-surface-50 rounded-2xl border border-surface-200 flex flex-col items-center justify-center text-center px-4">
        <p class="text-surface-600 font-medium mb-1">Нет ограничений</p>
        <p class="text-surface-400 text-sm max-w-96">Для этого элемента нет правил доступа. Он доступен всем студентам по умолчанию.</p>
      </div>

      <div class="flex flex-col gap-2">
        <!-- Существующие политики -->
        <PolicyRuleCard 
          v-for="policy in targetNode.data.policies" 
          :key="policy.id"
          :initial-data="policy"
          :target-node="targetNode"
          :tree-data="treeData"
          :edit-mode="true"
          @saved="handleSaved"
        />

        <!-- Новые (черновики) -->
        <PolicyRuleCard 
          v-for="newPol in newPolicies" 
          :key="newPol.id"
          :target-node="targetNode"
          :tree-data="treeData"
          :edit-mode="false"
          @saved="handleSaved"
          @cancelled="newPolicies = newPolicies.filter(p => p.id !== newPol.id)"
        />
      </div>

      <Button 
        v-if="newPolicies.length < 3"
        label="Добавить новое правило" 
        icon="pi pi-plus" 
        variant="outlined"
        class="w-full border-dashed py-4 bg-white/50 hover:bg-white hover:border-primary-400 transition-colors"
        @click="addNewPolicy"
      />
    </div>
  </div>
</template>

<style scoped>
/* Чтобы Button во Splitter не заезжала за прокрутку */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
