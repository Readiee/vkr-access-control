# experiments/ — фаза 3 ВКР

Эксперименты доказывают два положения на защиту: покрытие 9 типов правил через OWL+SWRL (положение 1) и обнаружение пяти классов дефектов через DL-резонер + граф (положение 2). Полный план — в `docs/PROJECT_BIBLE.md` §5.1. Старт фазы — 24.04.2026, досрочно против плановой даты 05.05.

## Состав

| # | Эксперимент | Что доказывает | Метрики |
|---|---|---|---|
| EXP1 | Верификация: СВ-1 Consistency + СВ-4 Redundancy + СВ-5 Subsumption | Новизна 3 | Precision/Recall/F1 per-property |
| EXP2 | Структура: СВ-2 Acyclicity + СВ-3 Reachability | Новизна 3 | Precision/Recall/F1 per-property |
| EXP3 | Корректность SWRL-вывода по 9 типам правил | Новизна 1, 2 | Accuracy по каждому типу |
| EXP4 | Производительность: scalability + latency cache-hit/miss | НФТ-1, НФТ-2, LIM4 | ms при 10/50/100/500 правилах |
| EXP5 | Сравнение с Moodle restrict access | Преимущества формального подхода | качественная таблица |
| EXP6 | Демо-сценарий happy_path | Работоспособность end-to-end | оформление готового кейса |
| EXP7 | Маппинг онтологии на 5 СДО | Платформо-независимость | таблица соответствий |

EXP1–EXP5 — основной трек дней 1–6. EXP6 и EXP7 уже закрыты по материалу (happy-path в `code/onto/scenarios/happy_path.py`, маппинг СДО в `docs/SAT_DATA_MODELS.md` §9), осталось оформление в буфере.

## Раскладка по дням

| День | Дата | Задача |
|---|---|---|
| 1 | 24.04 | Инфраструктура `experiments/` + EXP1 pilot на 8 существующих сценариях |
| 2 | 25.04 | EXP1 full: генератор, выборка 80–100 сценариев, итоговые P/R/F1 |
| 3 | 26.04 | EXP2: циклы и недостижимость, тот же поток |
| 4 | 27.04 | EXP3: accuracy по 9 типам на access matrix |
| 5 | 28.04 | EXP4: scalability + cache-hit/miss |
| 6 | 29.04 | EXP5: сравнение с Moodle restrict access |
| 7 | 30.04 | Оформление таблиц и графиков для главы 4 ПЗ |
| буфер | 01.05–04.05 | EXP6/EXP7 оформление, возвраты по замечаниям |

## Структура

```
experiments/
├── README.md                    # это
├── requirements.txt             # jupyter + pandas + matplotlib
├── .gitignore                   # scenarios/ и results/ локальные
├── _common/
│   ├── generator.py             # параметризованный OWL-генератор, seed=42
│   └── metrics.py               # confusion matrix, P/R/F1, форматтеры
├── exp1_verification/
│   ├── notebook.ipynb
│   ├── scenarios/               # сгенерированные OWL, локально
│   └── results/                 # CSV+PNG, копия в pz/figures/exp1/
├── exp2_structure/
├── exp3_rule_correctness/
├── exp4_performance/
└── exp5_moodle_comparison/
```

Ground truth для EXP1–EXP3 лежит в `code/backend/src/tests/fixtures/scenarios_ground_truth.json`, готовые OWL-сценарии — в `code/onto/ontologies/scenarios/`. Паттерн прогона через `VerificationService` копируется из `code/backend/src/tests/integration/test_verification_scenarios.py`.

## Запуск

Требуется Java Runtime (для Pellet через Owlready2) и Python 3.11+.

```bash
cd experiments
python -m venv .venv
.venv\Scripts\activate         # или source .venv/bin/activate на Linux
pip install -r requirements.txt
pip install -r ../code/backend/requirements.txt
jupyter notebook exp1_verification/notebook.ipynb
```

Ноутбуки импортируют код backend через `sys.path.append(...code/backend/src)`, отдельной установки backend-а как пакета не требуется.

Результаты ноутбука пишутся в `exp<N>/results/` (gitignored); финальные CSV и PNG экспортируются в `pz/figures/exp<N>/` при завершающей ячейке — оттуда подхватывает глава 4 ПЗ.

## Зафиксированные решения

Решения по инфраструктуре фазы 3 зафиксированы в `docs/PROJECT_BIBLE.md` §7, запись 24.04:

- Сгенерированные OWL не коммитятся; генератор детерминирован с `random.seed(42)`, воспроизводимость гарантирует пересборка.
- Ground truth для EXP3 строится независимым Python-интерпретатором политик (прямой цикл по ABox), сверяется с матрицей из `SAT_DATA_MODELS` §6.7 как cross-check.
- EXP4 замеры выполняются нативно, не в Docker. Железо и CPU governor фиксируются в ПЗ §4.1.
- PNG и CSV экспортируются в `pz/figures/exp*/` на финальной ячейке каждого ноутбука.

## Связь с тестами backend

Интеграционный тест `test_verification_scenarios.py` — это тот же прогон `VerificationService` по 8 сценариям, что и в pilot-ячейке EXP1, только завёрнутый в unittest. Он гарантирует, что сценарии стабильны и не регрессируют; ноутбук — собирает метрики и строит таблицы.

Если после изменения кода `services/verification/` сломался pilot-ноутбук — сначала запускается `pytest code/backend/src/tests/integration/test_verification_scenarios.py`, фикс идёт через тест, не через ноутбук.
