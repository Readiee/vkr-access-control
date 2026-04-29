from typing import Any, Optional

from core.enums import OWL_STATUS_PREFIX


def get_owl_prop(owl_individual: Any, property_name: str, default: Any = None) -> Any:
    """Нормализация чтения свойства OWL-индивида к «значение или default».

    Functional property отдаёт скаляр или None, non-functional — list ([] для пустого).
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


def status_value_from_individual(status_obj: Any) -> Optional[str]:
    """Снять префикс `status_` с OWL-индивида и отдать голое значение для UI."""
    if status_obj is None:
        return None
    name = getattr(status_obj, "name", None)
    if name is None:
        return None
    if name.startswith(OWL_STATUS_PREFIX):
        return name[len(OWL_STATUS_PREFIX):]
    return name
