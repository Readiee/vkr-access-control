workspace "VKR Access Control" "Система управления правилами доступа к образовательному контенту в СДО на основе OWL+SWRL с формальной верификацией. Магистерская ВКР ИТМО, см. docs/PROJECT_BIBLE.md §3.5.1." {

    !identifiers hierarchical

    properties {
        "structurizr.dsl.identifier" "workspace"
    }

    model {
        methodist = person "Методист" "Проектирует курс и правила доступа к активностям и модулям. Запускает верификацию, анализирует отчёты."
        admin     = person "Администратор" "Импортирует курсы из внешних СДО, ведёт аудит, управляет правилами для пулов курсов."

        lms = softwareSystem "Внешняя СДО" "Moodle, Canvas, Blackboard, Open edX, Stepik или СДО Дистех. Публикует контент студентам и запрашивает у нашей системы решения о доступе." {
            tags "External"
        }

        accessControl = softwareSystem "Система управления правилами доступа" "База правил в OWL+SWRL, DL-reasoning, графовая верификация, API для интеграции со внешними СДО." {

            webUI = container "Web UI" "Редактор правил, симулятор сценариев (UC-7a/b/c), отчёты верификации, интерфейс импорта." "Vue 3 + PrimeVue (SPA)" {
                tags "Web Browser"
            }

            apiBackend = container "API Backend" "REST API для UC-1…UC-10. Оркестрация reasoning, графовый анализ, агрегация завершённости, CWA-enforcement, инвалидация кэша." "Python 3.11 + FastAPI + Owlready2 + NetworkX" {

                group "API Layer" {
                    policyController       = component "PolicyController"       "CRUD правил с предварительной валидацией (UC-1, UC-2, UC-3)."                 "FastAPI router + Pydantic"
                    accessController       = component "AccessController"       "Решение о доступе к ресурсу для студента с объяснением (UC-4, UC-9)."         "FastAPI router"
                    progressController     = component "ProgressController"     "Приём событий прогресса, запуск восходящей агрегации (UC-5, UC-8)."           "FastAPI router"
                    verificationController = component "VerificationController" "Запуск полной верификации курса по СВ-1, СВ-2, СВ-3, СВ-4, СВ-5 (UC-6)." "FastAPI router"
                    simulationController   = component "SimulationController"   "Песочница: гипотетический студент, изменение фактов, карта доступа (UC-7)."    "FastAPI router"
                    integrationController  = component "IntegrationController"  "Импорт структуры и правил, webhook-события от внешней СДО (UC-5, UC-10)."      "FastAPI router"
                }

                group "Service Layer" {
                    policyService       = component "PolicyService"       "Создание, обновление, удаление правил с предпроверкой (ФТ-1, ФТ-5)."                 "Python service"
                    accessService       = component "AccessService"       "Cache-first решение о доступе, cache miss → reasoning, обратная цепочка (ФТ-2, ФТ-6)." "Python service"
                    verificationService = component "VerificationService" "Полная верификация курса (ФТ-3): СВ-1 (consistency) и СВ-4, СВ-5 через ReasoningOrchestrator; СВ-2 (acyclicity), СВ-3 (reachability) через GraphValidator." "Python service"
                    simulationService   = component "SimulationService"   "Сценарии песочницы на изолированной копии ABox (ФТ-7)."                               "Python service"
                    rollupService       = component "RollupService"       "Восходящая агрегация завершённости А3 (ФТ-8)."                                        "Python service"
                    integrationService  = component "IntegrationService"  "Импорт из СДО, нормализация форматов, автозапуск верификации (ФТ-4)."                 "Python service"
                }

                group "Core Layer" {
                    ontologyCore          = component "OntologyCore"          "Обёртка Owlready2: load/save, операции TBox/ABox, транзакции."                             "Owlready2"
                    reasoningOrchestrator = component "ReasoningOrchestrator" "Pipeline А2: enricher (now(), roll-up) → Pellet → CWA-enforcement → таймаут + fallback. Pellet встроен как embedded JVM через JPype, отдельным процессом не деплоится." "Python + JPype + Pellet 2.x (embedded JVM)"
                    graphValidator        = component "GraphValidator"        "Split-node DiGraph А1, DFS cycle detection, reachability А4."                              "NetworkX"
                    cacheManager          = component "CacheManager"          "GET/SET/DEL решений, инвалидация затронутых ключей (А5)."                                  "redis-py"
                }
            }

            ontologyStore = container "Ontology Store" "OWL 2 DL онтология: TBox (классы, аксиомы, SWRL-шаблоны) + ABox (факты курса)." ".owl файл (RDF/XML)" {
                tags "Storage"
            }

            cache = container "Cache" "Кэш решений о доступе. Fallback при таймауте reasoning (НФТ-3)." "Redis 7" {
                tags "Cache"
            }
        }

        // ── Context level ────────────────────────────────────────────────
        methodist -> accessControl "Создаёт правила, запускает верификацию, работает с симулятором" "HTTPS"
        admin     -> accessControl "Импортирует курсы, ведёт аудит правил"                          "HTTPS"
        lms           -> accessControl "Запросы доступа, события прогресса, импорт" "HTTPS/REST"
        accessControl -> lms           "Решения о доступе, объяснения блокировок"   "HTTPS/REST"

        // ── Container level ──────────────────────────────────────────────
        methodist -> accessControl.webUI "Управляет правилами, сценарии симулятора" "HTTPS"
        admin     -> accessControl.webUI "Импортирует и администрирует"             "HTTPS"

        accessControl.webUI      -> accessControl.apiBackend "Вызовы UC-1…UC-10"        "HTTPS/JSON"
        lms                      -> accessControl.apiBackend "Запросы доступа, webhooks" "HTTPS/REST"
        accessControl.apiBackend -> lms                      "Объяснения блокировок"    "HTTPS/REST"

        accessControl.apiBackend -> accessControl.ontologyStore "Чтение и запись онтологии" "Owlready2 I/O"
        accessControl.apiBackend -> accessControl.cache         "Чтение и запись кэша"       "Redis protocol"

        // ── Component level: Controllers ← внешние клиенты ───────────────
        accessControl.webUI -> accessControl.apiBackend.policyController       "Управление правилами"          "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.accessController       "Проверка доступа в симуляторе" "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.verificationController "Запуск верификации"            "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.simulationController   "Сценарии симулятора"           "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.integrationController  "Запуск импорта"                "HTTPS/JSON"

        lms -> accessControl.apiBackend.accessController      "Запросы доступа"        "HTTPS/REST"
        lms -> accessControl.apiBackend.progressController    "События прогресса"      "HTTPS/REST (webhook)"
        lms -> accessControl.apiBackend.integrationController "Импорт и синхронизация" "HTTPS/REST"

        // ── Component level: Controllers → Services ──────────────────────
        accessControl.apiBackend.policyController       -> accessControl.apiBackend.policyService       "Делегирует" "Python call"
        accessControl.apiBackend.accessController       -> accessControl.apiBackend.accessService       "Делегирует" "Python call"
        accessControl.apiBackend.progressController     -> accessControl.apiBackend.rollupService       "Делегирует" "Python call"
        accessControl.apiBackend.verificationController -> accessControl.apiBackend.verificationService "Делегирует" "Python call"
        accessControl.apiBackend.simulationController   -> accessControl.apiBackend.simulationService   "Делегирует" "Python call"
        accessControl.apiBackend.integrationController  -> accessControl.apiBackend.integrationService  "Делегирует" "Python call"

        // ── Component level: Services → Core ─────────────────────────────
        accessControl.apiBackend.policyService -> accessControl.apiBackend.graphValidator        "Проверка ацикличности"         "Python call"
        accessControl.apiBackend.policyService -> accessControl.apiBackend.reasoningOrchestrator "Проверка консистентности"      "Python call"
        accessControl.apiBackend.policyService -> accessControl.apiBackend.ontologyCore          "Изменение TBox/ABox"           "Python call"
        accessControl.apiBackend.policyService -> accessControl.apiBackend.cacheManager          "Инвалидация затронутых ключей" "Python call"

        accessControl.apiBackend.accessService -> accessControl.apiBackend.cacheManager          "Cache lookup / store"  "Python call"
        accessControl.apiBackend.accessService -> accessControl.apiBackend.reasoningOrchestrator "Cache miss → reasoning" "Python call"
        accessControl.apiBackend.accessService -> accessControl.apiBackend.ontologyCore          "Чтение ABox"            "Python call"

        accessControl.apiBackend.verificationService -> accessControl.apiBackend.graphValidator        "СВ-2, СВ-3"         "Python call"
        accessControl.apiBackend.verificationService -> accessControl.apiBackend.reasoningOrchestrator "СВ-1, СВ-4, СВ-5"   "Python call"
        accessControl.apiBackend.verificationService -> accessControl.apiBackend.ontologyCore          "Чтение TBox + ABox" "Python call"

        accessControl.apiBackend.simulationService -> accessControl.apiBackend.ontologyCore  "Работа с копией ABox"                    "Python call"
        accessControl.apiBackend.simulationService -> accessControl.apiBackend.accessService "Запрос решений (разрешённое исключение)" "Python call"

        accessControl.apiBackend.rollupService -> accessControl.apiBackend.ontologyCore "Чтение структуры, запись состояний" "Python call"
        accessControl.apiBackend.rollupService -> accessControl.apiBackend.cacheManager "Инвалидация после прогресса"        "Python call"

        accessControl.apiBackend.integrationService -> accessControl.apiBackend.ontologyCore         "Запись структуры и правил"                  "Python call"
        accessControl.apiBackend.integrationService -> accessControl.apiBackend.rollupService        "Первичная агрегация после импорта"          "Python call"
        accessControl.apiBackend.integrationService -> accessControl.apiBackend.verificationService  "Автоверификация (разрешённое исключение)"   "Python call"

        // ── Component level: Core → соседние контейнеры ──────────────────
        accessControl.apiBackend.ontologyCore          -> accessControl.ontologyStore                    "Загрузка и сохранение .owl" "Owlready2 I/O"
        accessControl.apiBackend.reasoningOrchestrator -> accessControl.apiBackend.ontologyCore          "Инжекция и CWA-enforcement" "Python call"
        accessControl.apiBackend.cacheManager          -> accessControl.cache                            "GET/SET/DEL"                "Redis protocol"
    }

    views {
        
        systemContext accessControl "Context" "Уровень 1 C4 — системный контекст: участники процесса и внешняя СДО." {
            include *
            autolayout lr 300 200
        }

        container accessControl "Containers" "Уровень 2 C4 — контейнеры системы. Reasoning встроен в API Backend (Pellet + JPype, не отдельный процесс)." {
            include *
            autolayout lr 300 200
        }

        component accessControl.apiBackend "Overview" "Уровень 3 C4 — обзор компонентов API Backend. Три слоя: API, Service, Core. Без внешних контейнеров (для приложения ПЗ)." {
            include accessControl.apiBackend.policyController accessControl.apiBackend.accessController accessControl.apiBackend.progressController accessControl.apiBackend.verificationController accessControl.apiBackend.simulationController accessControl.apiBackend.integrationController
            include accessControl.apiBackend.policyService accessControl.apiBackend.accessService accessControl.apiBackend.verificationService accessControl.apiBackend.simulationService accessControl.apiBackend.rollupService accessControl.apiBackend.integrationService
            include accessControl.apiBackend.ontologyCore accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.graphValidator accessControl.apiBackend.cacheManager
            autolayout tb 250 180
        }

        component accessControl.apiBackend "PolicyFlow" "Уровень 3 C4 — поток управления правилами (UC-1, UC-2, UC-3). Создание/обновление правила с валидацией консистентности и ацикличности. API Layer скрыт — см. Overview." {
            include accessControl.webUI
            include accessControl.apiBackend.policyService
            include accessControl.apiBackend.graphValidator accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.ontologyCore accessControl.apiBackend.cacheManager
            include accessControl.ontologyStore accessControl.cache
            autolayout lr 200 150
        }

        component accessControl.apiBackend "AccessEvaluation" "Уровень 3 C4 — оценка доступа и симулятор (UC-4, UC-7, UC-9). Cache-first решение, cache miss → reasoning. Симулятор переиспользует AccessService. API Layer скрыт — см. Overview." {
            include accessControl.webUI lms
            include accessControl.apiBackend.accessService accessControl.apiBackend.simulationService
            include accessControl.apiBackend.cacheManager accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.ontologyCore
            include accessControl.cache accessControl.ontologyStore
            autolayout lr 200 150
        }

        component accessControl.apiBackend "Verification" "Уровень 3 C4 — полная верификация курса (UC-6). Проверка пяти свойств СВ-1…СВ-5. API Layer скрыт — см. Overview." {
            include accessControl.webUI
            include accessControl.apiBackend.verificationService
            include accessControl.apiBackend.graphValidator accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.ontologyCore
            include accessControl.ontologyStore
            autolayout lr 200 150
        }

        component accessControl.apiBackend "IntegrationRollup" "Уровень 3 C4 — импорт курса и агрегация прогресса (UC-5, UC-8, UC-10). После импорта — автоверификация; при событии прогресса — каскадное roll-up. API Layer скрыт — см. Overview." {
            include accessControl.webUI lms
            include accessControl.apiBackend.integrationService accessControl.apiBackend.rollupService accessControl.apiBackend.verificationService
            include accessControl.apiBackend.ontologyCore accessControl.apiBackend.cacheManager
            include accessControl.ontologyStore accessControl.cache
            autolayout lr 200 150
        }

        styles {
            element "Person" {
                shape person
                background #1168bd
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
            element "External" {
                background #8b8b8b
                color #ffffff
            }
            element "Web Browser" {
                shape WebBrowser
            }
            element "Storage" {
                shape cylinder
            }
            element "Cache" {
                shape cylinder
                background #d94a3d
                color #ffffff
            }
        }
    }
}
