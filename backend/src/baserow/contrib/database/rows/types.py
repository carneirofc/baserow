from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple, NewType, TypedDict, TypeVar

from django.db.models import QuerySet

from baserow.contrib.database.field_rules.collector import CascadeUpdatedRows
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.core.action.registries import ActionType
from baserow.core.action.signals import ActionCommandType

GeneratedTableModelForUpdate = NewType(
    "GeneratedTableModelForUpdate", GeneratedTableModel
)

RowsForUpdate = NewType("RowsForUpdate", QuerySet)


class FileImportConfiguration(TypedDict):
    upsert_fields: list[int]
    upsert_values: list[list[Any]]
    skipped_fields: list[int]


class FileImportDict(TypedDict):
    data: list[list[Any]]
    configuration: FileImportConfiguration | None


FieldsMetadata = NewType("FieldsMetadata", dict[str, Any])
RowValues = NewType("RowValues", dict[str, Any])
RowId = NewType("RowId", int)


class UpdatedRowsData(NamedTuple):
    updated_rows: list[GeneratedTableModelForUpdate]
    updated_rows_values: list[RowValues]
    original_rows_values_by_id: dict[RowId, RowValues]
    updated_fields_metadata_by_row_id: dict[RowId, FieldsMetadata]
    errors: dict[int, dict[str, Any]] | None = None
    updated_field_ids: Iterable[int] | None = None

    # use cascade update fields to propagate rows that weren't requested
    # by the user to be updated, but were updated by various operations in the
    # code (i.e. field rules).
    cascade_update: CascadeUpdatedRows | None = None


@dataclass
class ImportChangeCollector:
    """
    Accumulates the before/after row data a file import needs in order to write
    per-cell row history, bounded by `max_entries`.

    A bulk import can touch hundreds of thousands of rows; keeping every original
    value in memory and writing a history entry for each would dwarf the import
    itself. Once the budget is spent the collector stops recording and flags itself
    as `truncated`, which the import's compliance record surfaces.

    `max_entries` of 0 disables collection entirely.
    """

    max_entries: int = 0
    created_row_ids: list[int] = field(default_factory=list)
    created_rows_values: list[dict[str, Any]] = field(default_factory=list)
    created_fields_metadata_by_row_id: dict[int, dict[str, Any]] = field(
        default_factory=dict
    )
    updated_row_ids: list[int] = field(default_factory=list)
    updated_rows_values: list[dict[str, Any]] = field(default_factory=list)
    original_rows_values_by_id: dict[int, dict[str, Any]] = field(default_factory=dict)
    updated_fields_metadata_by_row_id: dict[int, dict[str, Any]] = field(
        default_factory=dict
    )
    deleted_row_ids: list[int] = field(default_factory=list)
    deleted_rows_values: list[dict[str, Any]] = field(default_factory=list)
    deleted_fields_metadata_by_row_id: dict[int, dict[str, Any]] = field(
        default_factory=dict
    )
    # Totals for the whole import, as opposed to the capped per-row detail above.
    updated_row_count: int = 0
    deleted_row_count: int = 0
    trashed_rows_entry_id: int | None = None
    truncated: bool = False

    @property
    def enabled(self) -> bool:
        return self.max_entries > 0

    @property
    def remaining(self) -> int:
        collected = (
            len(self.created_row_ids)
            + len(self.updated_row_ids)
            + len(self.deleted_row_ids)
        )
        return max(self.max_entries - collected, 0)

    def collect_updated(self, updated: "UpdatedRowsData") -> None:
        """
        Records the rows an update touched, up to the remaining budget.
        """

        rows = list(updated.updated_rows)
        # Counted before the budget applies: the summary must stay complete even when
        # the per-row detail is capped.
        self.updated_row_count += len(rows)

        if not self.enabled:
            return

        budget = self.remaining
        if len(rows) > budget:
            self.truncated = True
            rows = rows[:budget]
        if not rows:
            return

        row_ids = [row.id for row in rows]
        values_by_id = {
            values["id"]: values
            for values in updated.updated_rows_values
            if "id" in values
        }
        for row_id in row_ids:
            self.updated_row_ids.append(row_id)
            self.updated_rows_values.append(values_by_id.get(row_id, {"id": row_id}))
            self.original_rows_values_by_id[row_id] = (
                updated.original_rows_values_by_id.get(row_id, {})
            )
            self.updated_fields_metadata_by_row_id[row_id] = (
                updated.updated_fields_metadata_by_row_id.get(row_id, {})
            )

    def collect_created(
        self,
        row_ids: list[int],
        rows_values: list[dict[str, Any]],
        fields_metadata_by_row_id: dict[int, dict[str, Any]],
    ) -> None:
        """
        Records the rows an import created, up to the remaining budget.
        """

        if not self.enabled:
            return

        budget = self.remaining
        if len(row_ids) > budget:
            self.truncated = True
            row_ids = row_ids[:budget]
            rows_values = rows_values[:budget]
        if not row_ids:
            return

        self.created_row_ids.extend(row_ids)
        self.created_rows_values.extend(rows_values)
        for row_id in row_ids:
            self.created_fields_metadata_by_row_id[row_id] = (
                fields_metadata_by_row_id.get(row_id, {})
            )

    def collect_deleted(
        self,
        row_ids: list[int],
        rows_values: list[dict[str, Any]],
        fields_metadata_by_row_id: dict[int, dict[str, Any]],
    ) -> None:
        """
        Records the rows a replace removed, up to the remaining budget.
        """

        if not self.enabled:
            return

        budget = self.remaining
        if len(row_ids) > budget:
            self.truncated = True
            row_ids = row_ids[:budget]
            rows_values = rows_values[:budget]
        if not row_ids:
            return

        self.deleted_row_ids.extend(row_ids)
        self.deleted_rows_values.extend(rows_values)
        for row_id in row_ids:
            self.deleted_fields_metadata_by_row_id[row_id] = (
                fields_metadata_by_row_id.get(row_id, {})
            )


class CreatedRowsData(NamedTuple):
    created_rows: list[GeneratedTableModel]
    errors: dict[int, dict[str, Any]] | None = None
    updated_field_ids: list[int] | None = None
    cascade_update: CascadeUpdatedRows | None = None


FieldName = NewType("FieldName", str)

# Dict of table_id -> row_id -> field_name ->
# {added: List[row_id], removed:List[row_id], metadata: Dict}
RelatedRowsDiff = dict[int, dict[int, dict[str, dict[str, Any]]]]


@dataclass
class ActionData:
    """
    A container for action params to be used in post-action handlers
    """

    uuid: str
    type: "ActionType"
    timestamp: datetime
    command_type: ActionCommandType
    params: dict[str, Any]


class RowChangeDiff(NamedTuple):
    """
    Represents the diff between the before and after values of a row. It
    contains the names of the fields that have changed, as well as the before
    and after values of those fields.
    """

    row_id: int
    table_id: int
    changed_field_names: list[FieldName]
    before_values: dict[FieldName, Any]
    after_values: dict[FieldName, Any]


ActionTypeVar = TypeVar("ActionTypeVar", bound=ActionType)
