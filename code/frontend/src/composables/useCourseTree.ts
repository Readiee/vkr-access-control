import { ref, watch } from 'vue';

/**
 * Общая логика для управления состоянием дерева курса:
 * выделение, развёртывание, реактивность
 *
 * @param treeDataRef функция или computed, возвращающие текущие данные дерева
 */
export function useCourseTree(treeDataRef: () => any[] | undefined) {
  const selectedNodeKey = ref<Record<string, boolean>>({});
  const selectedNode = ref<any>(null);
  const expandedKeys = ref<Record<string, boolean>>({});

  // Автоматически разворачиваем корневой узел при первой загрузке
  // и восстанавливаем выделение при обновлениях
  watch(treeDataRef, (newTree) => {
    if (newTree && newTree.length > 0) {
      if (Object.keys(expandedKeys.value).length === 0) {
        expandedKeys.value = { [newTree[0].key]: true };
      }
      
      // Восстанавливаем ссылку на выбранный узел при обновлении дерева,
      // иначе старая ссылка указывает на узел из прошлого снимка
      if (selectedNode.value && selectedNode.value.key) {
        const findNode = (nodes: any[], key: string): any => {
          for (const node of nodes) {
            if (node.key === key) return node;
            if (node.children) {
              const found = findNode(node.children, key);
              if (found) return found;
            }
          }
          return null;
        };
        const freshNode = findNode(newTree, selectedNode.value.key);
        if (freshNode) {
          selectedNode.value = freshNode;
        }
      }
    } else {
      expandedKeys.value = {};
    }
  }, { immediate: true, deep: true });

  const onNodeSelect = (node: any) => {
    selectedNode.value = node;
  };

  return { selectedNodeKey, selectedNode, expandedKeys, onNodeSelect };
}
