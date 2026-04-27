<?php
// Спецификация Custom Moodle availability condition plugin (НЕ runnable).
//
// Полная директория плагина при реализации: availability/condition/external_pdp/
// Состав: classes/condition.php (этот файл), classes/frontend.php, lang/en/...,
// db/install.xml, version.php. Регистрация в Moodle — стандартная процедура
// availability-плагинов: после копирования каталога Moodle обнаружит плагин
// при следующем заходе администратора в /admin/index.php.
//
// Назначение: при рендере страницы курса Moodle вызывает is_available()
// для каждой видимой активности; плагин делегирует решение нашему PDP через
// REST API и блокирует элемент при отрицательном ответе. Источник истины —
// наша онтология; локальные availability conditions Moodle игнорируются
// (см. SAT_DATA_MODELS §10.3).

namespace availability_external_pdp;

defined('MOODLE_INTERNAL') || die();

class condition extends \core_availability\condition {

    /**
     * @param object $structure Структура условия из JSON
     */
    public function __construct($structure) {
        // У плагина нет собственных параметров: вся логика на стороне PDP.
    }

    public function save() {
        return (object) ['type' => 'external_pdp'];
    }

    public function is_available($not, \core_availability\info $info, $grabthelot, $userid) {
        $config = get_config('availability_external_pdp');
        $cmid   = $info->get_context()->instanceid;

        $url = sprintf(
            '%s/api/v1/access/student/student_%d/element/activity_%d',
            rtrim($config->pdp_url, '/'),
            $userid,
            $cmid
        );

        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT_MS     => 200,  // НФТ-1 жёсткий budget
            CURLOPT_HTTPHEADER     => ['Authorization: Bearer ' . $config->api_token],
        ]);
        $response = curl_exec($ch);
        $http     = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        if (curl_errno($ch) || $http !== 200) {
            // Fail-close по принципу least privilege (NIST SP 800-162).
            $this->reason = get_string('pdp_unavailable', 'availability_external_pdp');
            curl_close($ch);
            return false;
        }
        curl_close($ch);

        $verdict = json_decode($response, true);
        $allow   = !empty($verdict['accessible']);
        if (!$allow) {
            $this->reason = self::format_unmet_conditions($verdict['unmet_conditions'] ?? []);
        }

        // XOR с $not: если в правиле задан NOT-модификатор — инвертируем.
        return $allow XOR $not;
    }

    public function get_description($full, $not, \core_availability\info $info) {
        return get_string($not ? 'requires_not_available_external' : 'requires_available_external',
            'availability_external_pdp');
    }

    protected function get_debug_string() {
        return 'external_pdp';
    }

    private static function format_unmet_conditions(array $conditions): string {
        if (empty($conditions)) {
            return get_string('blocked_default', 'availability_external_pdp');
        }
        $parts = [];
        foreach ($conditions as $condition) {
            $parts[] = sprintf(
                '%s: требуется %s',
                $condition['type'] ?? 'unknown',
                $condition['target'] ?? '—'
            );
        }
        return implode('; ', $parts);
    }
}
