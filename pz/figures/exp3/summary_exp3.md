# Эксперимент 2 — корректность SWRL-вывода по 9 типам правил

## Accuracy по типам правил

| Тип правила | Ячеек | Совпало | Accuracy |
|---|---|---|---|
| completion_required | 10 | 10 | 1.000 |
| grade_required | 10 | 10 | 1.000 |
| viewed_required | 7 | 7 | 1.000 |
| competency_required | 10 | 10 | 1.000 |
| date_restricted | 13 | 13 | 1.000 |
| group_restricted | 10 | 10 | 1.000 |
| aggregate_required | 7 | 7 | 1.000 |
| and_combination | 7 | 7 | 1.000 |
| or_combination | 7 | 7 | 1.000 |
| default_allow | 320 | 320 | 1.000 |
| **ИТОГО** | **401** | **401** | **1.000** |

## Accuracy по кейсам

| Кейс | Ячеек | Совпало | Accuracy |
|---|---|---|---|
| happy_path | 80 | 80 | 1.000 |
| var_completion | 39 | 39 | 1.000 |
| var_grade | 36 | 36 | 1.000 |
| var_viewed | 36 | 36 | 1.000 |
| var_competency | 33 | 33 | 1.000 |
| var_date | 33 | 33 | 1.000 |
| var_group | 33 | 33 | 1.000 |
| var_aggregate | 39 | 39 | 1.000 |
| var_and | 36 | 36 | 1.000 |
| var_or | 36 | 36 | 1.000 |

## Итог

Общая accuracy: **1.000** на 401 ячейках access matrix (10 ABox, happy_path + 9 variants).

Результат означает: SWRL-каталог (10 шаблонов + мета-правило + H-1/H-2) выводит access matrix, совпадающую с независимым Python-интерпретатором прямой проверки условий. Для каждого из 9 типов правил покрытие достаточно для обобщения.

## Допущения

- Pellet принимается как W3C-compliant reasoner (Sirin 2007), его корректность не исследуется.
- Интерпретатор написан по прямой читке `code/onto/scripts/2_rules_setup.py`, не использует код VerificationService/AccessService. Это даёт независимую реализацию спеки.
- `dt.datetime.utcnow()` в интерпретаторе синхронизирован с `CurrentTime` enricher (оба подкладывают одно и то же текущее время перед reasoning).
