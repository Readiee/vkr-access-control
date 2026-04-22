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
