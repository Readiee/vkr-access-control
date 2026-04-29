from typing import Any


def get_owl_prop(owl_individual: Any, property_name: str, default: Any = None) -> Any:
    """Первое значение свойства у OWL-индивида (работает для list и scalar API).

    Non-functional property возвращает list ([] для пустого); functional —
    скаляр (или None). Единая функция нормализует к «либо значение, либо default».
    """
    value = getattr(owl_individual, property_name, None)
    if value is None:
        return default
    if isinstance(value, list):
        return value[0] if value else default
    return value


def label_or_name(obj: Any) -> str:
    """rdfs:label[0] или техническое имя индивида; пустая строка для None

    Используется в UI и трейсах: пользователь видит rdfs:label если он задан,
    fallback — onto-name индивида
    """
    if obj is None:
        return ""
    label = getattr(obj, "label", None)
    return label[0] if label else obj.name
