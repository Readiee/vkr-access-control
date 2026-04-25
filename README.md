# OntoRule

Управление правилами доступа к образовательному контенту через OWL 2 DL + SWRL,
с автоматической верификацией: непротиворечивость онтологии, ацикличность графа
зависимостей, достижимость элементов, обнаружение избыточных и поглощённых
правил.

Демо-стек целиком: онтология, бэкенд, фронт, кэш, демо-сценарии.

## Стек

- **Онтология**: OWL 2 DL + SWRL, [Owlready2](https://owlready2.readthedocs.io/), резонер [Pellet](https://github.com/stardog-union/pellet) через JVM
- **Backend**: Python 3.11+, FastAPI, Pydantic, Redis
- **Frontend**: Vue 3, TypeScript, Vite, PrimeVue
- **Инфраструктура**: Docker Compose (backend + frontend + redis), JRE 17 для Pellet

## Быстрый старт

```bash
docker compose -f code/docker-compose.yml up --build
```

После сборки:

- Web UI: <http://localhost:8080>
- Swagger backend: <http://localhost:8000/docs>
- Health backend: <http://localhost:8000/>

Подробнее про известные проблемы запуска (DNS на debian-зеркалах) — в [code/README.md](code/README.md).

## Что внутри

```
.
├── code/
│   ├── backend/         FastAPI + Owlready2 + резонер
│   ├── frontend/        Vue/Vite + PrimeVue
│   ├── onto/            OWL-онтология, SWRL-правила, демо-сценарии
│   └── docker-compose.yml
├── experiments/         Воспроизводимые замеры (verify, performance, accuracy)
├── diagrams/            DSL-исходники архитектурных и UML-диаграмм
├── docs/                Внутренняя проектная документация
└── pz/                  Текст работы (отдельный артефакт, не часть кода)
```

## Запуск без Docker

Бэкенд:

```bash
pip install -r code/backend/requirements.txt
cd code/backend/src
uvicorn main:app --reload
```

Фронт:

```bash
cd code/frontend
npm install
npm run dev
```

Redis должен быть доступен; при `redis=None` бэкенд работает в режиме «без кэша»
(default-deny + полный пересчёт каждый запрос, медленно, но корректно).

## Тесты

```bash
pip install -r code/backend/requirements-dev.txt
cd code/backend
python -m pytest src/tests/ -q --cov=src/services --cov=src/utils
```

Текущее покрытие: 117 тестов, 84% overall, Core Layer ≥82%. Прогон с реальным Pellet — ~2 минуты.

Frontend type-check и сборка:

```bash
cd code/frontend
npm run build
```

## Демо-данные

В образ backend копируется готовый TBox с правилами
(`code/onto/ontologies/edu_ontology_with_rules.owl`). Для генерации
демо-ABox и негативных сценариев:

```bash
cd code/onto/scripts && python 3_seed_demo_data.py
cd ../scenarios && python happy_path.py
```

## Лицензия

Внутренний проект, лицензия не определена.
