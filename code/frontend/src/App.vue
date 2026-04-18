<script setup lang="ts">
import { watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { toastQueue } from '@/utils/toastService';
import Toast from 'primevue/toast';

const toast = useToast();

watch(
  () => toastQueue.value,
  (newVal) => {
    if (newVal.length > 0) {
      newVal.forEach((msg) => {
        toast.add(msg);
      });
      toastQueue.value = [];
    }
  },
  { deep: true }
);
</script>

<template>
  <Toast />
  <router-view />
</template>
