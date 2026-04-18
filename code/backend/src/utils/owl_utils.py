from typing import Any, Optional

def get_owl_prop(owl_individual: Any, property_name: str, default: Any = None) -> Any:
    """
    Безопасно извлекает первое значение свойства из OWL-индивида.
    Решает проблему IndexError при пустых списках owlready2.
    """
    prop_list = getattr(owl_individual, property_name, [])
    if prop_list and isinstance(prop_list, list) and len(prop_list) > 0:
        return prop_list[0]
    return default
