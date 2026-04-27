<?php
// Спецификация PHP-плагина-наблюдателя событий Moodle (НЕ runnable).
//
// Размещается в local/external_pdp/classes/observer.php при полной реализации.
// Регистрация подписок выполняется в local/external_pdp/db/events.php:
//
//   $observers = [
//     ['eventname' => '\\core\\event\\course_module_completion_updated',
//      'callback'  => '\\local_external_pdp\\observer::handle_completion_updated'],
//     ['eventname' => '\\mod_quiz\\event\\attempt_submitted',
//      'callback'  => '\\local_external_pdp\\observer::handle_quiz_attempt_submitted'],
//     ['eventname' => '\\mod_assign\\event\\submission_graded',
//      'callback'  => '\\local_external_pdp\\observer::handle_assign_submission_graded'],
//   ];
//
// Назначение: при каждом событии прогресса студент → активность плагин шлёт
// webhook на нашу систему (POST /api/v1/events/progress). Идемпотентность
// обеспечивается upsert-семантикой ProgressRepository в нашей системе.

namespace local_external_pdp;

defined('MOODLE_INTERNAL') || die();

class observer {

    public static function handle_completion_updated(
        \core\event\course_module_completion_updated $event
    ) {
        $config = get_config('local_external_pdp');
        $payload = [
            'student_id'  => 'student_' . $event->relateduserid,
            'element_id'  => 'activity_' . $event->contextinstanceid,
            'event_type'  => self::map_completion_state($event->other['completionstate']),
            'grade'       => self::fetch_grade($event->relateduserid, $event->contextinstanceid),
            'timestamp'   => gmdate('c', $event->timecreated),
        ];
        self::dispatch($config, $payload);
    }

    public static function handle_quiz_attempt_submitted(
        \mod_quiz\event\attempt_submitted $event
    ) {
        $config = get_config('local_external_pdp');
        $payload = [
            'student_id'  => 'student_' . $event->relateduserid,
            'element_id'  => 'activity_' . $event->contextinstanceid,
            'event_type'  => 'graded',
            'grade'       => self::fetch_quiz_grade($event->objectid),
            'timestamp'   => gmdate('c', $event->timecreated),
        ];
        self::dispatch($config, $payload);
    }

    public static function handle_assign_submission_graded(
        \mod_assign\event\submission_graded $event
    ) {
        $config = get_config('local_external_pdp');
        $payload = [
            'student_id'  => 'student_' . $event->relateduserid,
            'element_id'  => 'activity_' . $event->contextinstanceid,
            'event_type'  => 'graded',
            'grade'       => self::fetch_assign_grade($event->objectid),
            'timestamp'   => gmdate('c', $event->timecreated),
        ];
        self::dispatch($config, $payload);
    }

    private static function dispatch($config, array $payload) {
        $url = rtrim($config->pdp_url, '/') . '/api/v1/events/progress';
        $ch  = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 2,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $config->api_token,
            ],
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode($payload),
        ]);
        $response = curl_exec($ch);
        $http     = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if (curl_errno($ch) || $http !== 200) {
            // At-least-once: сохранить в локальный буфер для повторной отправки
            // reconciliation worker-ом (см. SAT_DATA_MODELS §11.6).
            self::enqueue_retry($payload);
        }
        curl_close($ch);
    }

    private static function map_completion_state(int $state): string {
        return match ($state) {
            1 => 'completed',
            2 => 'completed',
            3 => 'failed',
            default => 'viewed',
        };
    }

    private static function fetch_grade(int $userid, int $cmid): ?float {
        // Заглушка спецификации: реальная имплементация обращается к
        // grade_grades по grade_items.iteminstance == cm.instance.
        return null;
    }

    private static function fetch_quiz_grade(int $attemptid): ?float {
        // Спецификация: SELECT sumgrades FROM mdl_quiz_attempts WHERE id = ?
        return null;
    }

    private static function fetch_assign_grade(int $gradeid): ?float {
        // Спецификация: SELECT grade FROM mdl_assign_grades WHERE id = ?
        return null;
    }

    private static function enqueue_retry(array $payload): void {
        // Спецификация: INSERT в локальную таблицу external_pdp_retry,
        // обработку выполняет cron-task local_external_pdp\\task\\retry_dispatch.
    }
}
