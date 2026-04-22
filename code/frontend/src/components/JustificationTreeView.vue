<script setup lang="ts">
import type { JustificationNode } from '@/types';

defineProps<{
  node: JustificationNode;
  depth: number;
}>();

const statusSeverity: Record<string, 'success' | 'danger' | 'info' | 'secondary'> = {
  satisfied: 'success',
  available: 'success',
  unsatisfied: 'danger',
  unavailable: 'danger',
};

const formatValue = (v: unknown): string => {
  if (v === null || v === undefined) return '∅';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};
</script>

<template>
  <div
    class="rounded-lg border p-3 text-sm"
    :class="[
      node.status === 'satisfied' || node.status === 'available'
        ? 'border-green-100 bg-green-50/50'
        : 'border-red-100 bg-red-50/50',
      depth > 0 ? 'ml-4 mt-2' : '',
    ]"
  >
    <div class="flex flex-wrap items-center gap-2 mb-2">
      <Tag
        :severity="statusSeverity[node.status] ?? 'secondary'"
        :value="node.status"
      />
      <code class="text-xs text-surface-700">{{ node.rule_template }}</code>
      <code v-if="node.policy_id" class="text-xs text-surface-500">{{ node.policy_id }}</code>
    </div>

    <div v-if="node.note" class="text-surface-700 mb-2">{{ node.note }}</div>

    <div
      v-if="node.variable_bindings && Object.keys(node.variable_bindings).length"
      class="text-xs text-surface-600 mb-2"
    >
      <div class="font-semibold mb-1">Bindings:</div>
      <ul class="space-y-0.5">
        <li v-for="(v, k) in node.variable_bindings" :key="k">
          <code>?{{ k }}</code> = <code>{{ formatValue(v) }}</code>
        </li>
      </ul>
    </div>

    <div
      v-if="node.body_facts && node.body_facts.length"
      class="text-xs text-surface-600 mb-2"
    >
      <div class="font-semibold mb-1">Body facts:</div>
      <ul class="space-y-0.5">
        <li v-for="(f, i) in node.body_facts" :key="i">
          <code>{{ f.predicate }}({{ f.subject ?? '∅' }}, {{ formatValue(f.object) }})</code>
        </li>
      </ul>
    </div>

    <div v-if="node.children && node.children.length">
      <JustificationTreeView
        v-for="(child, i) in node.children"
        :key="i"
        :node="child"
        :depth="depth + 1"
      />
    </div>
  </div>
</template>
