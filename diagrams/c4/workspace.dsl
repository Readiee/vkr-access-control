workspace "Access Control" "C4-модель системы контроля доступа" {

    model {
        user = person "Пользователь" "Сотрудник организации, запрашивает доступ к ресурсам."
        admin = person "Администратор" "Управляет политиками и ролями."

        accessControl = softwareSystem "Система контроля доступа" "Управляет аутентификацией и авторизацией." {
            webApp = container "Web UI" "Интерфейс администратора." "React"
            api = container "API" "REST API для авторизации и управления." "Node.js"
            db = container "База данных" "Пользователи, роли, политики." "PostgreSQL" "Database"
        }

        user -> accessControl "Запрашивает доступ"
        admin -> webApp "Управляет политиками"
        webApp -> api "Вызывает" "HTTPS/JSON"
        api -> db "Читает/пишет" "SQL"
    }

    views {
        systemContext accessControl "Context" {
            include *
            autolayout lr
        }

        container accessControl "Containers" {
            include *
            autolayout lr
        }

        theme default
    }
}
