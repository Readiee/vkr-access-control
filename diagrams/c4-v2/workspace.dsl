workspace "VKR Access Control v2" "Система управления правилами доступа к образовательному контенту в СДО на основе OWL+SWRL с формальной верификацией. Версия с rule_handlers (реестр стратегий для диспетчеризации по типам правил). Магистерская ВКР ИТМО, см. docs/PROJECT_BIBLE.md §3.5.1." {

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

            webUI = container "Web UI" "Редактор правил, симулятор сценариев, отчёты верификации, интерфейс импорта." "Vue 3 + PrimeVue (SPA)" {
                tags "Web Browser"
            }

            apiBackend = container "API Backend" "REST API для всех сценариев. Оркестрация reasoning, графовый анализ, агрегация завершённости, принудительное закрытие мира, инвалидация кэша." "Python 3.11 + FastAPI + Owlready2 + NetworkX" {

                group "API Layer" {
                    policyController       = component "PolicyController"       "Создание, обновление, удаление правил с предварительной валидацией."          "FastAPI router + Pydantic"
                    accessController       = component "AccessController"       "Решение о доступе к ресурсу для студента и объяснение блокировки."             "FastAPI router"
                    progressController     = component "ProgressController"     "Приём событий прогресса от внешней СДО и запуск восходящей агрегации."         "FastAPI router"
                    verificationController = component "VerificationController" "Запуск полной верификации курса по пяти свойствам: консистентность, ацикличность, достижимость, атомарная невыполнимость, структурная достижимость." "FastAPI router"
                    sandboxController      = component "SandboxController"      "Песочница: гипотетический студент, изменение фактов, карта доступа."           "FastAPI router"
                    integrationController  = component "IntegrationController"  "Импорт структуры и правил, приём webhook-событий от внешней СДО."              "FastAPI router"
                }

                group "Service Layer" {
                    policyService       = component "PolicyService"       "Создание, обновление, удаление правил с предпроверкой ацикличности и консистентности."             "Python service"
                    accessService       = component "AccessService"       "Cache-first решение о доступе, cache miss → reasoning, обратная цепочка для объяснений."           "Python service"
                    progressService     = component "ProgressService"     "Приём события прогресса, запись в ABox, запуск reasoning, триггер каскадной агрегации."             "Python service"
                    verificationService = component "VerificationService" "Полная верификация курса: консистентность, атомарная невыполнимость и структурная достижимость через ReasoningOrchestrator; ацикличность и достижимость в графе через GraphValidator." "Python service"
                    sandboxService      = component "SandboxService"      "Сценарии песочницы на изолированной копии ABox."                                                       "Python service"
                    rollupService       = component "RollupService"       "Восходящая агрегация завершённости (от листьев к корню курса)."                                        "Python service"
                    integrationService  = component "IntegrationService"  "Импорт из внешней СДО, нормализация форматов, автозапуск верификации."                                 "Python service"
                }

                group "Rule Handler Registry" {
                    ruleHandlerRegistry = component "RuleHandlerRegistry" "Реестр стратегий: 9 хэндлеров по типу правила (7 атомарных + 2 составных). Диспетчеризация для GraphValidator, PolicyService и VerificationService." "Python package: rule_handlers"
                }

                group "Core Layer" {
                    ontologyCore          = component "OntologyCore"          "Обёртка Owlready2: load/save, операции TBox/ABox, транзакции."                              "Owlready2"
                    reasoningOrchestrator = component "ReasoningOrchestrator" "Pipeline вывода: предобработка фактов (now(), агрегация) → Pellet → принудительное закрытие мира → таймаут с fallback. Pellet встроен как embedded JVM через JPype, отдельным процессом не деплоится." "Python + JPype + Pellet 2.x (embedded JVM)"
                    graphValidator        = component "GraphValidator"        "Split-node-граф зависимостей: обнаружение циклов (DFS), проверка достижимости. Дуги строятся через RuleHandlerRegistry."  "NetworkX"
                    cacheManager          = component "CacheManager"          "Чтение, запись, удаление решений; инвалидация затронутых ключей."                            "redis-py"
                }
            }

            ontologyStore = container "Ontology Store" "OWL 2 DL онтология: TBox (классы, аксиомы, SWRL-шаблоны) + ABox (факты курса)." ".owl файл (RDF/XML)" {
                tags "Storage"
            }

            cache = container "Cache" "Кэш решений о доступе. Fallback при таймауте reasoning." "Redis 7" {
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

        accessControl.webUI      -> accessControl.apiBackend "Вызовы API"               "HTTPS/JSON"
        lms                      -> accessControl.apiBackend "Запросы доступа, webhooks" "HTTPS/REST"
        accessControl.apiBackend -> lms                      "Объяснения блокировок"    "HTTPS/REST"

        accessControl.apiBackend -> accessControl.ontologyStore "Чтение и запись онтологии" "Owlready2 I/O"
        accessControl.apiBackend -> accessControl.cache         "Чтение и запись кэша"       "Redis protocol"

        // ── Component level: Controllers ← внешние клиенты ───────────────
        accessControl.webUI -> accessControl.apiBackend.policyController       "Управление правилами"          "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.accessController       "Проверка доступа в симуляторе" "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.verificationController "Запуск верификации"            "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.sandboxController      "Сценарии симулятора"           "HTTPS/JSON"
        accessControl.webUI -> accessControl.apiBackend.integrationController  "Запуск импорта"                "HTTPS/JSON"

        lms -> accessControl.apiBackend.accessController      "Запросы доступа"        "HTTPS/REST"
        lms -> accessControl.apiBackend.progressController    "События прогресса"      "HTTPS/REST (webhook)"
        lms -> accessControl.apiBackend.integrationController "Импорт и синхронизация" "HTTPS/REST"

        // ── Component level: Controllers → Services ──────────────────────
        accessControl.apiBackend.policyController       -> accessControl.apiBackend.policyService       "Делегирует" "Python call"
        accessControl.apiBackend.accessController       -> accessControl.apiBackend.accessService       "Делегирует" "Python call"
        accessControl.apiBackend.progressController     -> accessControl.apiBackend.progressService     "Делегирует" "Python call"
        accessControl.apiBackend.verificationController -> accessControl.apiBackend.verificationService "Делегирует" "Python call"
        accessControl.apiBackend.sandboxController      -> accessControl.apiBackend.sandboxService      "Делегирует" "Python call"
        accessControl.apiBackend.integrationController  -> accessControl.apiBackend.integrationService  "Делегирует" "Python call"

        accessControl.apiBackend.progressService -> accessControl.apiBackend.ontologyCore          "Запись прогресса в ABox"      "Python call"
        accessControl.apiBackend.progressService -> accessControl.apiBackend.reasoningOrchestrator "Перерасчёт после события"     "Python call"
        accessControl.apiBackend.progressService -> accessControl.apiBackend.rollupService         "Каскадная агрегация"          "Python call"
        accessControl.apiBackend.progressService -> accessControl.apiBackend.accessService         "Инвалидация кэша студента"    "Python call"

        // ── Component level: Services → RuleHandlerRegistry ──────────────
        accessControl.apiBackend.policyService       -> accessControl.apiBackend.ruleHandlerRegistry "Запись типо-специфичных полей в ABox"                              "Python call"
        accessControl.apiBackend.verificationService -> accessControl.apiBackend.ruleHandlerRegistry "Проверка атомарной невыполнимости и структурной достижимости"      "Python call"
        accessControl.apiBackend.graphValidator      -> accessControl.apiBackend.ruleHandlerRegistry "Построение дуг зависимостей по типу правила"                       "Python call"

        // ── Component level: Services → Core ─────────────────────────────
        accessControl.apiBackend.policyService -> accessControl.apiBackend.graphValidator        "Проверка ацикличности"         "Python call"
        accessControl.apiBackend.policyService -> accessControl.apiBackend.reasoningOrchestrator "Проверка консистентности"      "Python call"
        accessControl.apiBackend.policyService -> accessControl.apiBackend.ontologyCore          "Изменение TBox/ABox"           "Python call"
        accessControl.apiBackend.policyService -> accessControl.apiBackend.cacheManager          "Инвалидация затронутых ключей" "Python call"

        accessControl.apiBackend.accessService -> accessControl.apiBackend.cacheManager          "Cache lookup / store"  "Python call"
        accessControl.apiBackend.accessService -> accessControl.apiBackend.reasoningOrchestrator "Cache miss → reasoning" "Python call"
        accessControl.apiBackend.accessService -> accessControl.apiBackend.ontologyCore          "Чтение ABox"            "Python call"

        accessControl.apiBackend.verificationService -> accessControl.apiBackend.graphValidator        "Ацикличность и достижимость"                                       "Python call"
        accessControl.apiBackend.verificationService -> accessControl.apiBackend.reasoningOrchestrator "Консистентность, атомарная невыполнимость, структурная достижимость" "Python call"
        accessControl.apiBackend.verificationService -> accessControl.apiBackend.ontologyCore          "Чтение TBox + ABox"                                                "Python call"

        accessControl.apiBackend.sandboxService -> accessControl.apiBackend.ontologyCore  "Работа с копией ABox"                    "Python call"
        accessControl.apiBackend.sandboxService -> accessControl.apiBackend.accessService "Запрос решений (разрешённое исключение)" "Python call"

        accessControl.apiBackend.rollupService -> accessControl.apiBackend.ontologyCore "Чтение структуры, запись состояний" "Python call"
        accessControl.apiBackend.rollupService -> accessControl.apiBackend.cacheManager "Инвалидация после прогресса"        "Python call"

        accessControl.apiBackend.integrationService -> accessControl.apiBackend.ontologyCore         "Запись структуры и правил"                  "Python call"
        accessControl.apiBackend.integrationService -> accessControl.apiBackend.rollupService        "Первичная агрегация после импорта"          "Python call"
        accessControl.apiBackend.integrationService -> accessControl.apiBackend.verificationService  "Автоверификация (разрешённое исключение)"   "Python call"

        // ── Component level: Core → соседние контейнеры ──────────────────
        accessControl.apiBackend.ontologyCore          -> accessControl.ontologyStore                    "Загрузка и сохранение .owl"                     "Owlready2 I/O"
        accessControl.apiBackend.reasoningOrchestrator -> accessControl.apiBackend.ontologyCore          "Инжекция фактов и принудительное закрытие мира" "Python call"
        accessControl.apiBackend.cacheManager          -> accessControl.cache                            "GET/SET/DEL"                                    "Redis protocol"
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

        component accessControl.apiBackend "Overview" "Уровень 3 C4 — обзор компонентов API Backend. Четыре группы: API, Service, Rule Handler Registry, Core. Без внешних контейнеров (для приложения ПЗ)." {
            include accessControl.apiBackend.policyController accessControl.apiBackend.accessController accessControl.apiBackend.progressController accessControl.apiBackend.verificationController accessControl.apiBackend.sandboxController accessControl.apiBackend.integrationController
            include accessControl.apiBackend.policyService accessControl.apiBackend.accessService accessControl.apiBackend.progressService accessControl.apiBackend.verificationService accessControl.apiBackend.sandboxService accessControl.apiBackend.rollupService accessControl.apiBackend.integrationService
            include accessControl.apiBackend.ruleHandlerRegistry
            include accessControl.apiBackend.ontologyCore accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.graphValidator accessControl.apiBackend.cacheManager
            autolayout tb 250 180
        }

        component accessControl.apiBackend "PolicyFlow" "Уровень 3 C4 — поток управления правилами. Создание/обновление правила: PolicyService записывает типо-специфичные поля через RuleHandlerRegistry, затем проверяет ацикличность (GraphValidator тоже через Registry) и консистентность. API Layer скрыт, см. Overview." {
            include accessControl.webUI
            include accessControl.apiBackend.policyService
            include accessControl.apiBackend.ruleHandlerRegistry
            include accessControl.apiBackend.graphValidator accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.ontologyCore accessControl.apiBackend.cacheManager
            include accessControl.ontologyStore accessControl.cache
            autolayout lr 200 150
        }

        component accessControl.apiBackend "AccessEvaluation" "Уровень 3 C4 — оценка доступа и симулятор. Cache-first решение, cache miss → reasoning. Симулятор переиспользует AccessService. API Layer скрыт, см. Overview." {
            include accessControl.webUI lms
            include accessControl.apiBackend.accessService accessControl.apiBackend.sandboxService
            include accessControl.apiBackend.cacheManager accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.ontologyCore
            include accessControl.cache accessControl.ontologyStore
            autolayout lr 200 150
        }

        component accessControl.apiBackend "Verification" "Уровень 3 C4 — полная верификация курса. VerificationService проверяет пять свойств: консистентность через ReasoningOrchestrator, ацикличность и достижимость через GraphValidator (тот строит граф через RuleHandlerRegistry), атомарную невыполнимость и структурную достижимость через RuleHandlerRegistry напрямую. API Layer скрыт, см. Overview." {
            include accessControl.webUI
            include accessControl.apiBackend.verificationService
            include accessControl.apiBackend.ruleHandlerRegistry
            include accessControl.apiBackend.graphValidator accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.ontologyCore
            include accessControl.ontologyStore
            autolayout lr 200 150
        }

        component accessControl.apiBackend "IntegrationRollup" "Уровень 3 C4 — импорт курса и каскадная агрегация прогресса. После импорта — автоверификация; при событии прогресса — каскадная агрегация и инвалидация кэша. API Layer скрыт, см. Overview." {
            include accessControl.webUI lms
            include accessControl.apiBackend.integrationService accessControl.apiBackend.progressService accessControl.apiBackend.rollupService accessControl.apiBackend.verificationService accessControl.apiBackend.accessService
            include accessControl.apiBackend.ontologyCore accessControl.apiBackend.reasoningOrchestrator accessControl.apiBackend.cacheManager
            include accessControl.ontologyStore accessControl.cache
            autolayout lr 200 150
        }

        component accessControl.apiBackend "RuleHandlerDispatch" "Уровень 3 C4 — диспетчеризация по типам правил (реестр стратегий). RuleHandlerRegistry вызывают три компонента: PolicyService (запись в ABox), VerificationService (атомарная невыполнимость и структурная достижимость) и GraphValidator (построение дуг зависимостей). Показывает, как 9 хэндлеров изолируют поведение каждого типа правила." {
            include accessControl.apiBackend.policyService
            include accessControl.apiBackend.verificationService
            include accessControl.apiBackend.graphValidator
            include accessControl.apiBackend.ruleHandlerRegistry
            include accessControl.apiBackend.ontologyCore
            autolayout tb 200 150
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
