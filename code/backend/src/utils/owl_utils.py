from typing import Any


def get_owl_prop(owl_individual: Any, property_name: str, default: Any = None) -> Any:
    """Первое значение свойства OWL-индивида (работает и для list, и для scalar API).

    Non-functional property возвращает list ([] для пустого), functional — скаляр
    или None. Здесь нормализуется к «либо значение, либо default».
    """
    value = getattr(owl_individual, property_name, None)
    if value is None:
        return default
    if isinstance(value, list):
        return value[0] if value else default
    return value


def label_or_name(obj: Any) -> str:
    """rdfs:label[0] или техническое имя индивида; "" для None."""
    if obj is None:
        return ""
    label = getattr(obj, "label", None)
    return label[0] if label else obj.name
