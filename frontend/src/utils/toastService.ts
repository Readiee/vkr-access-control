import { ref } from 'vue';

export interface ToastMessage {
  severity: 'success' | 'info' | 'warn' | 'error' | 'secondary' | 'contrast';
  summary: string;
  detail: string;
  life?: number;
}

export const toastQueue = ref<ToastMessage[]>([]);

export const toastService = {
  add(msg: ToastMessage) {
    toastQueue.value.push(msg);
  },
  showError(detail: string, summary = 'Ошибка') {
    this.add({ severity: 'error', summary, detail, life: 8000 });
  },
  showSuccess(detail: string, summary = 'Успех') {
    this.add({ severity: 'success', summary, detail, life: 3000 });
  },
  showInfo(detail: string, summary = 'Информация') {
    this.add({ severity: 'info', summary, detail, life: 3000 });
  },
  showWarn(detail: string, summary = 'Предупреждение') {
    this.add({ severity: 'warn', summary, detail, life: 3000 });
  }
};
