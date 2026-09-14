ROW_IMPORT_VALIDATION = "row-import-validation"
ROW_IMPORT_CREATION = "row-import-creation"

IMPORT_MODE_INSERT = "insert"
IMPORT_MODE_UPSERT = "upsert"
IMPORT_MODE_UPDATE = "update"
IMPORT_MODE_REPLACE = "replace"
IMPORT_MODES = [
    IMPORT_MODE_INSERT,
    IMPORT_MODE_UPSERT,
    IMPORT_MODE_UPDATE,
    IMPORT_MODE_REPLACE,
]
# The modes matching the imported rows with existing rows using `upsert_fields`.
IMPORT_MATCHING_MODES = [IMPORT_MODE_UPSERT, IMPORT_MODE_UPDATE]
