# EXP1 day 2 — full + adversarial

## Full (83 scenarios)

| Свойство | TP | FP | FN | TN | Precision | Recall | F1 | Support |
|---|---|---|---|---|---|---|---|---|
| consistency | 10 | 0 | 0 | 15 | 1.000 | 1.000 | 1.000 | 10 |
| acyclicity | 10 | 0 | 0 | 15 | 1.000 | 1.000 | 1.000 | 10 |
| reachability | 28 | 0 | 0 | 15 | 1.000 | 1.000 | 1.000 | 28 |
| redundancy | 10 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 10 |
| subsumption | 10 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 | 10 |
| **macro-avg** | . | . | . | . | 1.000 | 1.000 | 1.000 | . |

### Breakdown по типам дефектов

| Класс | Сценариев | Распознано | Accuracy |
|---|---|---|---|
| happy | 15 | 15 | 1.000 |
| sv1_disjointness | 10 | 10 | 1.000 |
| sv2_cycle | 10 | 10 | 1.000 |
| sv3_atomic_threshold | 10 | 10 | 1.000 |
| sv3_empty_date | 8 | 8 | 1.000 |
| sv3_structural | 10 | 10 | 1.000 |
| sv4_redundant | 10 | 10 | 1.000 |
| sv5_subject | 10 | 10 | 1.000 |

## Adversarial (19 scenarios)

| Свойство | TP | FP | FN | TN | Precision | Recall | F1 | Support |
|---|---|---|---|---|---|---|---|---|
| consistency | 0 | 0 | 0 | 19 | n/a | n/a | n/a | 0 |
| acyclicity | 0 | 0 | 0 | 19 | n/a | n/a | n/a | 0 |
| reachability | 0 | 0 | 0 | 19 | n/a | n/a | n/a | 0 |
| redundancy | 0 | 0 | 0 | 10 | n/a | n/a | n/a | 0 |
| subsumption | 0 | 0 | 0 | 10 | n/a | n/a | n/a | 0 |
| **macro-avg** | . | . | . | . | n/a | n/a | n/a | . |

### Breakdown по группам граничных кейсов

| Класс | Сценариев | Распознано | Accuracy |
|---|---|---|---|
| A_atomic_boundary | 5 | 5 | 1.000 |
| B_near_cycle | 4 | 4 | 1.000 |
| C_not_redundant | 5 | 5 | 1.000 |
| D_not_subsumed | 5 | 5 | 1.000 |

## Combined (full + adversarial, 102 scenarios)

| Свойство | TP | FP | FN | TN | Precision | Recall | F1 | Support |
|---|---|---|---|---|---|---|---|---|
| consistency | 10 | 0 | 0 | 34 | 1.000 | 1.000 | 1.000 | 10 |
| acyclicity | 10 | 0 | 0 | 34 | 1.000 | 1.000 | 1.000 | 10 |
| reachability | 28 | 0 | 0 | 34 | 1.000 | 1.000 | 1.000 | 28 |
| redundancy | 10 | 0 | 0 | 10 | 1.000 | 1.000 | 1.000 | 10 |
| subsumption | 10 | 0 | 0 | 10 | 1.000 | 1.000 | 1.000 | 10 |
| **macro-avg** | . | . | . | . | 1.000 | 1.000 | 1.000 | . |

## Параметры

- Full: 83 сценариев, генерация 1.7 с, верификация 93.5 с, среднее 1127 ms/case
- Adversarial: 19 сценариев, генерация 0.5 с, верификация 22.1 с, среднее 1162 ms/case
