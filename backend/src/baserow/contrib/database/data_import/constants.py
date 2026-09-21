IMPORT_MODE_APPEND = "append"
IMPORT_MODE_UPSERT = "upsert"
IMPORT_MODE_REPLACE = "replace"

IMPORT_MODES = [
    IMPORT_MODE_APPEND,
    IMPORT_MODE_UPSERT,
    IMPORT_MODE_REPLACE,
]

# The modes that mutate or destroy rows that already exist in the table. They require
# a strict, total column mapping so a file can never silently overwrite a subset of
# the table's data.
STRICT_IMPORT_MODES = [IMPORT_MODE_UPSERT, IMPORT_MODE_REPLACE]

IMPORT_RECORD_STATUS_RUNNING = "running"
IMPORT_RECORD_STATUS_FINISHED = "finished"
IMPORT_RECORD_STATUS_FAILED = "failed"

# The job progress state a replace reports while it trashes the current rows.
ROW_IMPORT_DELETION = "row-import-deletion"
