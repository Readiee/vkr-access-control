# Moodle adapter (PoC, режим Б)

Прототип адаптера интеграции с Moodle 4.x в режиме single PDP (см.
`docs/SAT_DATA_MODELS.md` §10–§11). Источник истины политик — наша онтология;
Moodle выступает чистым PEP, обращающимся к нашему PDP через REST API.

Состав:

- `moodle_client.py` — обёртка над Moodle Web Services REST API;
- `translators.py` — маппинг сущностей Moodle на классы TBox;
- `adapter.py` — `MoodleCourseImporter`, оркестратор первоначального импорта;
- `docker-compose.moodle.yml` — bitnami/moodle 4.3 + bitnami/mariadb 11;
- `php/event_observer.php` — спецификация плагина наблюдателя событий
  (НЕ runnable, см. предупреждение в шапке файла);
- `php/availability_condition.php` — спецификация custom availability
  condition plugin (НЕ runnable).

Полная имплементация PHP-плагинов и пилотное внедрение совместно с
ООО «Дистех» вынесены в перспективы развития (см. `pz/05_conclusion.md`).

## Запуск Moodle

```bash
docker compose -f docker-compose.moodle.yml up -d
```

Готовность Moodle проверяется обращением к `http://localhost:8081/login/index.php`.
Учётные данные администратора: `admin` / `Moodle@dmin1`.

## Подготовка Web Services

1. Site administration → Plugins → Web services → Overview → пройти все
   шаги мастера (`Enable web services`, `Enable protocols`).
2. Site administration → Server → Web services → External services →
   создать сервис `OntoRule`, добавить функции:
   - `core_course_get_courses_by_field`
   - `core_course_get_contents`
   - `core_enrol_get_enrolled_users`
   - `core_group_get_course_groups`
   - `core_group_get_group_members`
   - `gradereport_user_get_grade_items`
   - `core_competency_list_course_competencies` (опционально)
3. Site administration → Server → Web services → Manage tokens → выпустить
   токен под существующим пользователем с ролью, имеющей право
   `webservice/rest:use` и доступ ко всем перечисленным функциям.

## Создание демонстрационного курса

В Moodle UI вручную создать курс с shortname `HAPPYPATH`, повторяющий
структуру `code/onto/scenarios/happy_path.py` (см. приложение В ПЗ):
четыре активности, три группы, четыре компетенции. Существующие
availability conditions Moodle при импорте игнорируются — задавать их
не требуется.

## Запуск импорта

```bash
python -m integrations.moodle.adapter \
    --moodle-url http://localhost:8081 \
    --moodle-token <выпущенный_токен> \
    --pdp-url http://localhost:8000 \
    --course-shortname HAPPYPATH
```

После завершения импортёр выводит статистику. Серверная часть автоматически
запускает верификацию импортированной структуры (UC-6).

## Known issues

- **Группы и студенты передаются отдельными вызовами.** В текущей DSL §40
  endpoint `POST /api/v1/groups` и `POST /api/v1/students/batch` — заглушки
  на стороне адаптера: PoC рассчитан на ручную сверку через Web UI после
  импорта. Полная регистрация в `IntegrationService` — следующий шаг
  фазы интеграции.
- **Gradebook возвращает только итоговые оценки.** Промежуточные попытки
  Moodle через `gradereport_user_get_grade_items` не передаются; для PoC
  это приемлемо, в продуктивной интеграции попытки приходят через
  `event_observer.php` в реальном времени.
- **Файл `course_modules.availability` Moodle не разбирается.** Это часть
  выбора режима Б: политики хранятся только в нашей онтологии. Если в
  существующем Moodle-курсе уже есть availability conditions, их нужно
  будет переописать через UI методиста разработанной системы.
