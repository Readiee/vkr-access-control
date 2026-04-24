# EXP4 Performance — результаты (24.04)

## Железо

- python: `3.14.3`
- platform: `Windows-11-10.0.26200-SP0`
- processor: `Intel64 Family 6 Model 154 Stepping 3, GenuineIntel`
- machine: `AMD64`
- cpu_count: `12`

## Scalability (UC-6 verify, 3 прогона на размер)

| n_policies | runs | reason mean, ms | verify mean, ms | total mean, ms | total min, ms | total max, ms | stdev |
|---|---|---|---|---|---|---|---|
| 10 | 3 | 1182 | 1124 | 2306 | 2222 | 2404 | 91 |
| 50 | 3 | 1352 | 1412 | 2764 | 2697 | 2823 | 64 |
| 100 | 3 | 1499 | 2134 | 3633 | 3595 | 3683 | 45 |
| 500 | 3 | 2310 | 5751 | 8061 | 7835 | 8381 | 285 |

![scalability](scalability_exp4.png)

## Cache latency (30 прогонов hit/miss + 5 прогонов cold_miss)

| Режим | n | min | median | mean | p95 | p99 | max | stdev |
|---|---|---|---|---|---|---|---|---|
| hit | 30 | 1.20 | 1.35 | 1.38 | 1.53 | 1.61 | 2.04 | 0.16 |
| miss | 30 | 3.62 | 4.23 | 4.24 | 4.63 | 4.96 | 5.70 | 0.40 |
| cold_miss | 5 | 1326.49 | 1377.56 | 1396.97 | 1439.32 | 1439.32 | 1466.49 | 55.80 |

![latency](latency_exp4.png)

## Соответствие НФТ

- **НФТ-1** cache hit ≤50 ms: hit mean=1.38 ms, p99=1.61 ms — запас порядка.
- **НФТ-2** cache miss ≤2000 ms (cold start: World + load + reasoning + AccessService): mean=1397 ms, p95=1439 ms — соответствует.
- **НФТ-3** reasoning timeout 10 с (UC-6 verify на 500 правил): mean=8061 ms — соответствует.

UC-6 verify на 500 правил (7-8 с) не сверяется с НФТ-2 (access path, 2 с) — это UC-6 путь, верхняя граница в НФТ-3.
