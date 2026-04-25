# experiments/

Воспроизводимые замеры качества и производительности OntoRule. Каждый
эксперимент — Jupyter-ноутбук плюс набор py-модулей: генератор сценариев,
конфигурации прогонов, сборщики метрик. Результаты сохраняются как CSV и
PNG, скрипты детерминированные (`random.seed=42`).

## Состав

| Каталог | Что замеряет | Метрики |
|---|---|---|
| `exp1_verification/` | Обнаружение дефектов (consistency, redundancy, subsumption) | Precision / Recall / F1 per-property |
| `exp3_rule_correctness/` | Корректность вывода SWRL по 9 типам правил | Accuracy на access matrix |
| `exp4_performance/` | Время верификации и задержки чтения доступа | Время в мс при 10/50/100/500 политиках, p95/p99 для cache hit/miss |

## Структура

```
experiments/
├── _common/
│   ├── generator.py           параметризованный OWL-генератор
│   └── metrics.py             confusion matrix, P/R/F1, форматтеры md/csv
├── exp1_verification/
│   ├── notebook.ipynb         основной прогон + сборка отчёта
│   ├── sweep.py               конфигурация полной выборки сценариев
│   ├── adversarial.py         boundary-кейсы (false-positive guard)
│   └── results/               CSV и PNG, локальный артефакт прогона
├── exp3_rule_correctness/
│   ├── notebook.ipynb
│   ├── interpreter.py         независимый Python-интерпретатор политик (ground truth)
│   └── variants.py            ABox-варианты для увеличения per-type sample size
└── exp4_performance/
    ├── notebook.ipynb
    └── bench.py               scalability_run, latency_run, cold_miss_run
```

## Запуск

Требуется Java Runtime (для Pellet через Owlready2) и Python 3.11+.

```bash
cd experiments
python -m venv .venv
.venv\Scripts\activate         # Windows
# или: source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
pip install -r ../code/backend/requirements.txt
jupyter notebook exp1_verification/notebook.ipynb
```

Ноутбуки импортируют код backend через `sys.path.append(...code/backend/src)`,
отдельной установки backend как пакета не требуется.

Результаты ноутбука пишутся в `exp<N>/results/` (gitignored).

## Зафиксированные решения

- Сгенерированные OWL не коммитятся; генератор детерминирован с `random.seed=42`,
  воспроизводимость гарантирует пересборка
- Ground truth для exp3 строится независимым Python-интерпретатором политик
  (прямой проход по ABox), сверяется с матрицей доступов из happy-path-сценария
- exp4 замеры выполняются нативно, не в Docker; железо и CPU governor
  фиксируются в шапке отчёта

## Связь с тестами backend

Интеграционный тест `code/backend/src/tests/integration/test_verification_scenarios.py`
прогоняет `VerificationService` по тем же 8 сценариям, что и пилот exp1, но
завёрнуто в unittest. Если после изменения кода `services/verification/`
сломался ноутбук — сначала запускается соответствующий integration-тест,
фикс идёт через тест.
