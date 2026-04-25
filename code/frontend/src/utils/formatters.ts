import { RuleType, ElementType, ProgressStatus } from '@/types';
import type { PolicyResponse, Competency } from '@/types';

// Словари

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
  [RuleType.AND_COMBINATION]:      { label: 'Составное условие (И)',      severity: 'info' },
  [RuleType.OR_COMBINATION]:       { label: 'Составное условие (ИЛИ)',     severity: 'info' },
  [RuleType.AGGREGATE_REQUIRED]:   { label: 'Агрегат',      severity: 'warn' },
};

/** Опции для Select из RuleTypeMap */
export const ruleTypeOptions = Object.entries(RuleTypeMap).map(([value, info]) => ({
  value,
  label: info.label,
}));

/** Названия агрегирующих функций в человекочитаемом виде */
export const AggregateFunctionLabels: Record<string, string> = {
  AVG: 'Средний балл',
  SUM: 'Сумма баллов',
  COUNT: 'Количество сданных',
};

/** Типы элементов, у которых может быть has_grade — только они годны для агрегата */
export const GRADABLE_ELEMENT_TYPES = new Set<string>(['test', 'practice', 'assignment']);

/** Дата из ISO/Date → ru-RU «дд.мм.гггг чч:мм»; пустой вход → пустая строка */
export const formatDate = (value: string | Date | null | undefined): string => {
  if (!value) return '';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/** Компактная дата без времени: «дд.мм.гггг» — для бейджей правил */
export const formatDateShort = (value: string | Date | null | undefined): string => {
  if (!value) return '';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

// Иерархическое дерево компетенций из плоского списка (для TreeSelect)

interface CompetencyTreeNode {
  key: string;
  label: string;
  data: Competency;
  children: CompetencyTreeNode[];
}

export const buildCompetencyTree = (flat: Competency[]): CompetencyTreeNode[] => {
  const map = new Map<string, CompetencyTreeNode>();
  flat.forEach((c) => {
    map.set(c.id, { key: c.id, label: c.name, data: c, children: [] });
  });
  const roots: CompetencyTreeNode[] = [];
  flat.forEach((c) => {
    const node = map.get(c.id)!;
    const parent = c.parent_id ? map.get(c.parent_id) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  });
  return roots;
};

// Рекурсивный поиск названия узла по ID в дереве

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

// Форматирование текста бейджа политики

export const formatPolicyBadgeText = (
  policy: PolicyResponse,
  treeNodes: any[],           // принимает дерево CourseTreeNode[]
  allCompetencies: Competency[],
): string => {
  const typeInfo = RuleTypeMap[policy.rule_type];
  const label = typeInfo ? typeInfo.label : policy.rule_type;
  const p: any = policy;
  let description = '';

  const targetName = (): string | null => {
    if (p.target_element_name) return p.target_element_name;
    if (policy.target_element_id) return findNodeNameById(treeNodes, policy.target_element_id);
    return null;
  };

  switch (policy.rule_type) {
    case RuleType.GRADE_REQUIRED: {
      const target = targetName() ?? '?';
      description = `${label}: ${policy.passing_threshold ?? '–'}+ («${target}»)`;
      break;
    }
    case RuleType.VIEWED_REQUIRED:
    case RuleType.COMPLETION_REQUIRED: {
      const target = targetName();
      description = target ? `${label} («${target}»)` : label;
      break;
    }
    case RuleType.COMPETENCY_REQUIRED: {
      const explicit = p.competency_name;
      const compId = policy.target_competency_id || p.competency_id;
      const fallback = allCompetencies.find(c => c.id === compId)?.name;
      description = `${label}: ${explicit || fallback || '?'}`;
      break;
    }
    case RuleType.DATE_RESTRICTED: {
      const from = policy.valid_from ? ` с ${formatDateShort(policy.valid_from)}` : '';
      const until = policy.valid_until ? ` по ${formatDateShort(policy.valid_until)}` : '';
      description = from || until ? `${label}:${from}${until}` : label;
      break;
    }
    case RuleType.GROUP_RESTRICTED: {
      description = `${label}: ${p.restricted_to_group_name || policy.restricted_to_group_id || '—'}`;
      break;
    }
    case RuleType.AND_COMBINATION:
    case RuleType.OR_COMBINATION: {
      const conj = policy.rule_type === RuleType.AND_COMBINATION ? ' и ' : ' или ';
      const subs = p.subpolicies_detail as Array<{ name?: string; id: string }> | undefined;
      if (subs?.length) {
        description = `${label}: ${subs.map((s) => `«${s.name || s.id}»`).join(conj)}`;
      } else {
        const count = policy.subpolicy_ids?.length ?? 0;
        description = `${label}: ${count} подусловий`;
      }
      break;
    }
    case RuleType.AGGREGATE_REQUIRED: {
      const fn = AggregateFunctionLabels[policy.aggregate_function ?? ''] || policy.aggregate_function || '?';
      const names: string[] = p.aggregate_element_names?.length
        ? p.aggregate_element_names
        : (policy.aggregate_element_ids || []).map((id: string) => findNodeNameById(treeNodes, id) ?? id);
      const list = names.length ? ` по ${names.map((n) => `«${n}»`).join(', ')}` : '';
      description = `${fn}${list} ≥ ${policy.passing_threshold ?? '?'}`;
      break;
    }
    default:
      description = label;
  }

  return policy.is_active ? description : `${description} [выключено]`;
};
