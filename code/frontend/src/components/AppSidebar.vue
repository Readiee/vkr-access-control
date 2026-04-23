<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();
const menuItems = [
  { label: 'Дашборд', icon: 'pi pi-home', route: '/' },
  { label: 'Верификация', icon: 'pi pi-shield', route: '/verify' },
  { label: 'Симулятор', icon: 'pi pi-users', route: '/simulator' }
];
</script>

<template>
  <aside class="w-64 bg-surface-0 border-r border-surface-200 flex flex-col transition-colors duration-200">
    <div class="h-16 flex items-center px-6 border-b border-surface-200 gap-2">
      <img src="/ontorule-hex.svg" alt="OntoRule" class="w-8 h-8" />
      <span class="text-xl font-bold text-surface-900 flex items-baseline">
        Onto<span class="text-primary-500">Rule</span>
      </span>
    </div>
    <nav class="flex-1 p-4 space-y-1">
      <button 
        v-for="item in menuItems" 
        :key="item.route"
        @click="router.push(item.route)"
        class="w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-left font-medium outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
        :class="[
          router.currentRoute.value.path === item.route 
            ? 'bg-primary-50 text-primary-600' 
            : 'text-surface-700 hover:bg-surface-100 hover:text-surface-900'
        ]"
      >
        <i :class="item.icon" class="text-lg"></i>
        {{ item.label }}
      </button>
    </nav>
  </aside>
</template>
