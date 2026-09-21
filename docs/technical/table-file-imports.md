# Table file imports

A user with the right permissions can refresh the contents of an existing table from an
uploaded spreadsheet. An import only ever writes cell values: it never adds, removes,
renames or retypes a field, so the table's data format is the same before and after.

## Modes

At upload time the user picks how the file is applied. Each mode is gated by its own
operation type, so a role can grant one without granting the others.

| Mode | What it does | Operation type |
| --- | --- | --- |
| `append` | Adds the file's rows to the ones already in the table. | `database.table.import_rows` |
| `upsert` | Updates the rows matched by the chosen field and adds the rest. | `database.table.upsert_rows` |
| `replace` | Moves every existing row to the trash, then adds the file's rows. | `database.table.replace_rows` |

`upsert` matches a file row against a table row by comparing the value of a field the
user picks in the import dialog. Matching is positional for repeated values: two rows
sharing a match value are paired with the table's rows in id order.

`replace` **trashes** the old rows rather than deleting them. The trash entry id is on
the import's record, so the previous contents can be restored afterwards.

All three modes are gated per workspace role through `CONTROLLABLE_OPERATIONS`
(`backend/src/baserow/core/roles/controllable_operations.py`), under the
`database_import` component.

## The strict column contract

`upsert` and `replace` change or destroy rows the table already has, so they refuse a
file whose columns don't line up with the table:

- every file column must be assigned to a field — nothing may be skipped,
- every **importable** field of the table must be covered by exactly one file column.

A field is importable when its type is writable and its `FieldType.can_import` is true.
Read-only types are never importable, and neither is `password`, which stores a hash a
spreadsheet cannot round-trip. `FieldType.can_import` must stay in sync with
`getCanImport()` on the matching frontend field type; the backend set is pinned by
`backend/tests/baserow/contrib/database/data_import/test_importable_field_types.py`.

The check runs twice: once synchronously in `AsyncTableImportView` so the user gets an
immediate `ERROR_TABLE_IMPORT_SCHEMA_MISMATCH` with the offending columns and fields,
and again in the job, against the locked table, before anything is written.

`append` keeps the lenient mapping it has always had — columns may be skipped and
fields left untouched.

## What every import leaves behind

Three independent trails, because each answers a different question.

### The import record

`TableImportRecord` (`backend/src/baserow/contrib/database/data_import/models.py`) is a
durable row per import: who ran it, from which IP, against which table, in which mode,
the original file name, the SHA-256 of the imported payload, the column mapping, the
row counts, the trash entry a replace produced, and the per-row error report.

It is deliberately not a `Job`, so `JobHandler.clean_up_jobs` never removes it, and
every relation is nullable with a denormalised name alongside it, so deleting the table,
database, workspace or user does not erase the record of what was done.

The record is opened in the request that starts the job, not in the job itself: a job
runs inside a transaction, so a failed import rolls back everything it wrote and could
not record its own failure. `reconcile_table_import_records`, a periodic task, gives a
final status to records whose job ended without one.

Read them with `GET /api/database/tables/{table_id}/import-records/`, which requires
`database.table.read`.

### Row history

`upsert` and `replace` register an action type of their own
(`upsert_rows_from_file`, `replace_rows_from_file`) with a matching
`RowHistoryProviderType`, so changed cells get before/after entries in the normal row
history, visible in the row's history panel.

This is capped: see `BASEROW_MAX_ROW_HISTORY_ENTRIES_PER_IMPORT` below. When the cap
bites, the record's `row_history_truncated` says so, and its counters stay complete.

These actions are **not** undoable. Undoing a replace of a large table would mean
carrying every removed row's values in the action's params; recovery goes through the
trash entry instead. `append` keeps the undoable `import_rows` action it has always had.

### The application log

Finishing or failing a record emits a structured line bound with
`compliance="table_import"`, carrying the record id, mode, table, user, payload digest
and row counts — the shape to ship into an external SIEM. Every action additionally
emits the generic `action_done` line from
`backend/src/baserow/core/action/signals.py`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `BASEROW_MAX_ROW_HISTORY_ENTRIES_PER_IMPORT` | `10000` | How many rows of one import get per-cell history. Above this, only the summary record is kept and it is flagged as truncated. |
| `BASEROW_TABLE_IMPORT_RECORD_RETENTION_DAYS` | `0` | How long import records are kept. `0` keeps them forever. |
| `BASEROW_TABLE_IMPORT_RECONCILE_INTERVAL_MINUTES` | `10` | How often stale records are given a final status and expired ones removed. |

Setting `BASEROW_ROW_HISTORY_RETENTION_DAYS=0` disables row history entirely, imports
included. The import records are unaffected by it.

## Concurrency

`FileImportJobType._can_schedule_or_raise` allows one import job per table, so a replace
and an upsert cannot race. The job body runs inside
`read_committed_single_table_transaction`, which also keeps the fields from being
changed while the import is validating against them.
