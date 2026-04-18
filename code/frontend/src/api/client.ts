import axios from 'axios'
import { toastService } from '@/utils/toastService'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: { 'Content-Type': 'application/json' }
})

// Глобальный перехватчик ответов
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail 
      || error.response?.data?.message 
      || 'Неизвестная ошибка сервера';
    
    toastService.showError(message);
    
    return Promise.reject(error);
  }
)

export default apiClient
