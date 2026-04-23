<script setup lang="ts">
import AppSidebar from '@/components/AppSidebar.vue';
</script>

<template>
  <div class="min-h-screen flex bg-surface-50 text-surface-900 transition-colors duration-200">
    <AppSidebar />

    <div class="flex-1 flex flex-col h-screen overflow-hidden">
      <main class="flex-1 overflow-y-auto p-4 layout-content shadow-[inset_0_2px_10px_rgba(0,0,0,0.02)]">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(5px);
}
</style>
