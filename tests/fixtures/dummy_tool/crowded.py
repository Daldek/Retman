"""Many parameterless operations in categories, to test two-stage recognition."""

from copy import deepcopy

from retman.i18n.loader import Texts
from retman.registry.operation import Operation


def crowded_operations(
    template: Operation, layout: dict[str, int]
) -> dict[str, Operation]:
    """``layout`` maps a category to its number of operations ``<category>_<n>``.

    Every operation copies ``template`` (an operation without parameters and
    inputs) and has the texts the recognition questions need, as do the
    categories (``Grupa <category>``, ``Operacja <category>_<n>``).
    """
    data: dict = {"operations": {}, "categories": {}}
    for category, count in layout.items():
        data["categories"][category] = {
            "label": f"Grupa {category}",
            "description": f"Opis grupy {category}",
        }
        for index in range(count):
            key = f"{category}_{index}"
            data["operations"][key] = {
                "label": f"Operacja {key}",
                "description": f"Opis operacji {key}",
            }
    texts = Texts(data, "crowded")
    return {
        f"{category}_{index}": Operation(
            {
                **deepcopy(template.spec),
                "id": f"{category}_{index}",
                "category": category,
            },
            template.tool,
            template.version,
            texts,
            template.client,
        )
        for category, count in layout.items()
        for index in range(count)
    }
