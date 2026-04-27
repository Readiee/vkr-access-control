# code/ — сборка и запуск

Минимум для воспроизведения демо: одна команда `docker compose up --build`.

## Что поднимается

| Сервис | Порт на хосте | Технология                                                             |
| ------------ | ------------------------ | -------------------------------------------------------------------------------- |
| `backend`  | `8000`                 | FastAPI + Owlready2 + Pellet (JRE)                                               |
| `frontend` | `8080`                 | Vue/Vite, раздаётся nginx,`/api/` проксируется в backend |
| `redis`    | `6379`                 | Redis 7 для кэша `access:*`                                             |

## Запуск

```bash
docker compose -f code/docker-compose.yml up --build
```

После сборки:

- Web UI: [http://localhost:8080](http://localhost:8080)
- Swagger backend: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health backend: [http://localhost:8000/](http://localhost:8000/)

## Известная проблема: build падает на установке JRE

Если backend build падает на `E: Unable to locate package default-jre-headless`
с ошибкой вида `Could not connect to debian.map.fastlydns.net:80 (127.89.x.x)` —
системный DNS резолвит debian-зеркала в loopback (антивирус, корпоративный
DNS, AdGuard).

Фикс: Docker Desktop → Settings → Docker Engine:

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

Apply & Restart, затем `docker compose up --build` заново.

## Данные онтологии

В образ backend копируется `code/onto/ontologies/edu_ontology_with_rules.owl`
(TBox + SWRL-правила).

Demo-ABox и негативные сценарии генерируются скриптами:

```bash
cd code/onto/scripts && python 3_seed_demo_data.py
cd ../scenarios && for s in bad_sv1_disjointness bad_sv2_cycle bad_sv3_atomic_threshold \
  bad_sv3_empty_date bad_sv3_structural bad_sv4_redundant bad_sv5_subject; do
    python "$s.py"
done
```

Результат: файлы в `code/onto/ontologies/scenarios/` плюс ground-truth
`code/backend/src/tests/fixtures/scenarios_ground_truth.json`.

## Тесты

Локальный запуск без Docker:

```bash
pip install -r code/backend/requirements-dev.txt
cd code/backend
python -m pytest src/tests/ -q --cov=src/services --cov=src/utils
```

Только unit-слой (без Pellet, ~2 секунды):

```bash
cd code/backend
python -m pytest src/tests/unit/ -q
```
