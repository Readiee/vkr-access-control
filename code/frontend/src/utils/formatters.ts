import { RuleType, ElementType, ProgressStatus } from '@/types';
import type { PolicyResponse, Competency } from '@/types';

// ---------------------------------------------------------------------------
// Словари
// ---------------------------------------------------------------------------

export const ElementTypeMap: Record<ElementType, string> = {
  [ElementType.COURSE]: 'Курс',
  [ElementType.MODULE]: 'Модуль',
  [ElementType.LECTURE]: 'Лекция',
  [ElementType.TEST]: 'Тест',
  [ElementType.ASSIGNMENT]: 'Задание',
  [ElementType.PRACTICE]: 'Практика',
};

export const ProgressStatusMap: Record<ProgressStatus, string> = {
  [ProgressStatus.VIEWED]: 'Просмотрено',
  [ProgressStatus.COMPLETED]: 'Завершено',
  [ProgressStatus.PASSED]: 'Сдано',
  [ProgressStatus.FAILED]: 'Провален'
};

export const ProgressStatusColorMap: Record<ProgressStatus, Severity> = {
  [ProgressStatus.VIEWED]: 'info',
  [ProgressStatus.COMPLETED]: 'success',
  [ProgressStatus.PASSED]: 'success',
  [ProgressStatus.FAILED]: 'danger'
};

export type Severity = 'info' | 'success' | 'warn' | 'danger' | 'secondary' | 'contrast';

export interface RuleTypeInfo {
  label: string;
  severity: Severity;
}

export const RuleTypeMap: Record<string, RuleTypeInfo> = {
  [RuleType.VIEWED_REQUIRED]:      { label: 'Просмотр',     severity: 'info' },
  [RuleType.COMPLETION_REQUIRED]:  { label: 'Завершение',   severity: 'success' },
  [RuleType.GRADE_REQUIRED]:       { label: 'Оценка',       severity: 'warn' },
  [RuleType.COMPETENCY_REQUIRED]:  { label: 'Компетенция',  severity: 'danger' },
  [RuleType.DATE_RESTRICTED]:      { label: 'Даты',         severity: 'secondary' },
  [RuleType.GROUP_RESTRICTED]:     { label: 'Группа',       severity: 'contrast' },
  [RuleType.AND_COMBINATION]:      { label: 'И (AND)',      severity: 'info' },
  [RuleType.OR_COMBINATION]:       { label: 'ИЛИ (OR)',     severity: 'info' },
  [RuleType.AGGREGATE_REQUIRED]:   { label: 'Агрегат',      severity: 'warn' },
};

/** Сгенерированные опции для Select из RuleTypeMap */
export const ruleTypeOptions = Object.entries(RuleTypeMap).map(([value, info]) => ({
  value,
  label: info.label,
}));

// ---------------------------------------------------------------------------
// Рекурсивный поиск названия узла по ID в дереве
// ---------------------------------------------------------------------------

export const findNodeNameById = (nodes: any[], id: string): string | null => {
  for (const node of nodes) {
    if (node.data && node.data.id === id) return node.data.name;
    if (node.children && node.children.length > 0) {
      const found = findNodeNameById(node.children, id);
      if (found) return found;
    }
  }
  return null;
};

// ---------------------------------------------------------------------------
// Функция форматирования текста бейджа
// ---------------------------------------------------------------------------

export const formatPolicyBadgeText = (
  policy: PolicyResponse,
  treeNodes: any[],           // принимает дерево CourseTreeNode[]
  allCompetencies: Competency[],
): string => {
  const typeInfo = RuleTypeMap[policy.rule_type];
  const label = typeInfo ? typeInfo.label : policy.rule_type;
  let description = '';

  switch (policy.rule_type) {
    case RuleType.GRADE_REQUIRED: {
      const target = policy.target_element_id
        ? (findNodeNameById(treeNodes, policy.target_element_id) ?? '?')
        : '?';
      description = `${label}: ${policy.passing_threshold ?? '–'}+ (${target})`;
      break;
    }
    case RuleType.VIEWED_REQUIRED:
    case RuleType.COMPLETION_REQUIRED: {
      const target = policy.target_element_id
        ? findNodeNameById(treeNodes, policy.target_element_id)
        : null;
      description = target ? `${label} (${target})` : label;
      break;
    }
    case RuleType.COMPETENCY_REQUIRED: {
      // Поддержка обоих вариантов ключа (с API и из дерева)
      const compId = policy.target_competency_id || (policy as any).competency_id;
      const comp = allCompetencies.find(c => c.id === compId)?.name || '?';
      description = `${label}: ${comp}`;
      break;
    }
    case RuleType.DATE_RESTRICTED: {
      const formatDate = (dateStr: string) => {
        // Парсим YYYY-MM-DDTHH:mm:ssZ в DD.MM.YYYY
        const [year, month, day] = dateStr.split('T')[0].split('-');
        return `${day}.${month}.${year}`;
      };
      const from = policy.valid_from ? ` с ${formatDate(policy.valid_from)}` : '';
      const until = policy.valid_until ? ` по ${formatDate(policy.valid_until)}` : '';
      description = from || until ? `${label}:${from}${until}` : label;
      break;
    }
    case RuleType.GROUP_RESTRICTED: {
      description = policy.restricted_to_group_id
        ? `${label}: ${policy.restricted_to_group_id}`
        : label;
      break;
    }
    case RuleType.AND_COMBINATION:
    case RuleType.OR_COMBINATION: {
      const count = policy.subpolicy_ids?.length ?? 0;
      description = `${label}: ${count} подполитик`;
      break;
    }
    case RuleType.AGGREGATE_REQUIRED: {
      const fn = policy.aggregate_function ?? '?';
      const cnt = policy.aggregate_element_ids?.length ?? 0;
      description = `${label}: ${fn} ≥ ${policy.passing_threshold ?? '?'} (${cnt} эл.)`;
      break;
    }
    default:
      description = label;
  }

  return policy.is_active ? description : `${description} [выключено]`;
};
