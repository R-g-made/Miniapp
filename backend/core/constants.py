from backend.models.enums import Language

SORTING_OPTIONS = {
    Language.RU: [
        {"id": "price_asc", "label": "Сначала дешевые"},
        {"id": "price_desc", "label": "Сначала дорогие"},
        {"id": "newest", "label": "Сначала новые"},
        {"id": "oldest", "label": "Сначала старые"}
    ],
    Language.EN: [
        {"id": "price_asc", "label": "Cheapest First"},
        {"id": "price_desc", "label": "Expensive First"},
        {"id": "newest", "label": "Newest First"},
        {"id": "oldest", "label": "Oldest First"}
    ]
}
