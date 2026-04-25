# frontend

Vue 3 + TypeScript + Vite + PrimeVue. SPA для управления политиками доступа,
просмотра отчётов верификации и симуляции прогресса студента.

## Команды

```bash
npm install              # установка зависимостей
npm run dev              # dev-сервер на http://localhost:5173
npm run build            # vue-tsc + vite build → dist/
npm run preview          # локальный просмотр production-сборки
```

## Переменные окружения

`VITE_API_BASE_URL` — базовый URL backend API. По умолчанию ожидается, что
nginx-прокси внутри Docker подменяет `/api/` → `backend:8000`. При локальной
разработке без Docker укажите явно в `.env.development`:

```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Структура

```
src/
├── api/             axios-обёртки над REST-эндпоинтами
├── components/      Vue-компоненты (редактор политик, симулятор, отчёт)
├── composables/     общие хуки
├── layout/          AppLayout
├── router/          vue-router
├── stores/          Pinia-сторы (онтология, песочница)
├── types/           TS-типы и enum
├── utils/           форматтеры, toast-сервис
└── views/           страницы (Dashboard, Sandbox, VerificationReport)
```
