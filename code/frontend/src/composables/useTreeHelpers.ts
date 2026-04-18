import { RuleType, ElementType } from '@/types';
import type { CourseTreeNode } from '@/types';

export function useTreeHelpers() {
  /**
   * Поиск пути до узла в иерархии (для Breadcrumbs).
   */
  const findPath = (nodes: CourseTreeNode[], targetId: string): Array<{ label: string }> => {
    for (const node of nodes) {
      if (node.data.id === targetId) return [{ label: node.data.name }];
      if (node.children?.length) {
        const subPath = findPath(node.children, targetId);
        if (subPath.length) return [{ label: node.data.name }, ...subPath];
      }
    }
    return [];
  };

  /**
   * Сбор ID предков и потомков целевого узла для блокировки циклов.
   */
  const getBlockedIds = (nodes: CourseTreeNode[], targetId: string): Set<string> => {
    const blocked = new Set<string>();

    // Рекурсивный поиск предков
    const collectAncestors = (ns: CourseTreeNode[], path: string[]): boolean => {
      for (const n of ns) {
        const newPath = [...path, n.data.id];
        if (n.data.id === targetId) {
          path.forEach(id => blocked.add(id));
          return true;
        }
        if (n.children?.length && collectAncestors(n.children, newPath)) {
          return true;
        }
      }
      return false;
    };

    // Сбор всех потомков
    const collectDescendants = (ns: CourseTreeNode[]) => {
      for (const n of ns) {
        blocked.add(n.data.id);
        if (n.children?.length) collectDescendants(n.children);
      }
    };

    collectAncestors(nodes, []);

    // Поиск самого узла для сбора его потомков
    const findNode = (ns: CourseTreeNode[]): CourseTreeNode | null => {
      for (const n of ns) {
        if (n.data.id === targetId) return n;
        if (n.children?.length) {
          const found = findNode(n.children);
          if (found) return found;
        }
      }
      return null;
    };

    const target = findNode(nodes);
    if (target?.children?.length) collectDescendants(target.children);

    return blocked;
  };

  /**
   * Умное раскрытие ключей дерева до целевого узла.
   */
  const getExpandedKeys = (treeData: CourseTreeNode[], targetId?: string): Record<string, boolean> => {
    const keys: Record<string, boolean> = {};
    if (!treeData.length) return keys;

    const course = treeData[0];
    if (course) keys[course.data.id] = true;

    if (targetId && course) {
      for (const module of course.children ?? []) {
        if (module.data.id === targetId) break;
        const inModule = module.children?.some((el: CourseTreeNode) => el.data.id === targetId);
        if (inModule) {
          keys[module.data.id] = true;
          break;
        }
      }
    }
    return keys;
  };

  /**
   * Построение дерева узлов с флагами selectable на основе типа правила и блокировок.
   * Теперь недопустимые узлы не удаляются, а помечаются как неактивные с пояснением.
   */
  const buildSelectableTree = (
    nodes: CourseTreeNode[],
    blockedIds: Set<string>,
    ruleType: RuleType | string,
    selfId?: string
  ): any[] => {
    return nodes.map(node => {
      const isSelf = node.data.id === selfId;
      const isBlockedByHierarchy = blockedIds.has(node.data.id);
      
      // Правило оценки нельзя вешать на лекции (у них нет баллов)
      const isInvalidTypeForGrade = ruleType === RuleType.GRADE_REQUIRED && node.data.type === ElementType.LECTURE;
      
      // Проверка по общей карте допустимых типов (опционально для расширения)
      const selectableTypes: Record<string, string[]> = {
        [RuleType.GRADE_REQUIRED]: [ElementType.TEST, ElementType.ASSIGNMENT, ElementType.PRACTICE],
        [RuleType.VIEWED_REQUIRED]: [ElementType.LECTURE, ElementType.PRACTICE],
        [RuleType.COMPLETION_REQUIRED]: [
          ElementType.LECTURE, 
          ElementType.TEST, 
          ElementType.ASSIGNMENT, 
          ElementType.PRACTICE, 
          ElementType.MODULE, 
          ElementType.COURSE
        ],
      };
      
      const allowed = selectableTypes[ruleType as string] ?? [];
      const isInvalidType = allowed.length > 0 && !allowed.includes(node.data.type as ElementType);

      const isSelectable = !isSelf && !isBlockedByHierarchy && !isInvalidType;

      let labelPostfix = '';
      if (isSelf) labelPostfix = ' [Текущий]';
      else if (isBlockedByHierarchy) labelPostfix = ' [Связан]';
      else if (isInvalidTypeForGrade) labelPostfix = ' [Без оценки]';
      else if (isInvalidType) labelPostfix = ' [Несовместим]';

      return {
        key: node.data.id,
        label: (node.data.name || node.label) + labelPostfix,
        selectable: isSelectable,
        // Визуальное оформление для невыбираемых узлов
        styleClass: isSelectable ? '' : 'opacity-50 cursor-not-allowed' + (isSelf ? ' font-bold text-primary-700' : ''),
        data: { type: node.data.type },
        children: node.children?.length
          ? buildSelectableTree(node.children, blockedIds, ruleType, selfId)
          : undefined,
      };
    });
  };

  return {
    findPath,
    getBlockedIds,
    getExpandedKeys,
    buildSelectableTree
  };
}
