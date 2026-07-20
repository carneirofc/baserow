from baserow.contrib.automation.nodes.operations import (
    CreateAutomationNodeOperationType,
    DeleteAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.workflows.operations import (
    CreateAutomationWorkflowOperationType,
    DeleteAutomationWorkflowOperationType,
    ReadAutomationWorkflowOperationType,
    UpdateAutomationWorkflowOperationType,
)
from baserow.contrib.builder.elements.operations import (
    CreateElementOperationType,
    DeleteElementOperationType,
    ReadElementOperationType,
    UpdateElementOperationType,
)
from baserow.contrib.builder.pages.operations import (
    CreatePageOperationType,
    DeletePageOperationType,
    ReadPageOperationType,
    UpdatePageOperationType,
)
from baserow.contrib.database.fields.operations import (
    CreateFieldOperationType,
    DeleteFieldOperationType,
    ReadFieldOperationType,
    UpdateFieldOperationType,
)
from baserow.contrib.database.operations import CreateTableDatabaseTableOperationType
from baserow.contrib.database.rows.operations import (
    DeleteDatabaseRowOperationType,
    ReadDatabaseRowOperationType,
    UpdateDatabaseRowOperationType,
)
from baserow.contrib.database.table.operations import (
    CreateRowDatabaseTableOperationType,
    DeleteDatabaseTableOperationType,
    ReadDatabaseTableOperationType,
    UpdateDatabaseTableOperationType,
)
from baserow.contrib.database.views.operations import (
    CreateViewOperationType,
    DeleteViewOperationType,
    ReadViewOperationType,
    UpdateViewOperationType,
)
from baserow.core.operations import (
    DeleteWorkspaceOperationType,
    ReadWorkspaceOperationType,
    UpdateWorkspaceOperationType,
)

# A curated grid of the operation types a workspace `Role` can be restricted to.
# Not every registered `OperationType` is exposed here (~200 exist, many obscure) -
# only the operations an operator is likely to want to grant/deny per component.
CONTROLLABLE_OPERATIONS = {
    "database_table": {
        "create": CreateTableDatabaseTableOperationType.type,
        "read": ReadDatabaseTableOperationType.type,
        "update": UpdateDatabaseTableOperationType.type,
        "delete": DeleteDatabaseTableOperationType.type,
    },
    "database_field": {
        "create": CreateFieldOperationType.type,
        "read": ReadFieldOperationType.type,
        "update": UpdateFieldOperationType.type,
        "delete": DeleteFieldOperationType.type,
    },
    "database_row": {
        "create": CreateRowDatabaseTableOperationType.type,
        "read": ReadDatabaseRowOperationType.type,
        "update": UpdateDatabaseRowOperationType.type,
        "delete": DeleteDatabaseRowOperationType.type,
    },
    "view": {
        "create": CreateViewOperationType.type,
        "read": ReadViewOperationType.type,
        "update": UpdateViewOperationType.type,
        "delete": DeleteViewOperationType.type,
    },
    "builder_page": {
        "create": CreatePageOperationType.type,
        "read": ReadPageOperationType.type,
        "update": UpdatePageOperationType.type,
        "delete": DeletePageOperationType.type,
    },
    "builder_element": {
        "create": CreateElementOperationType.type,
        "read": ReadElementOperationType.type,
        "update": UpdateElementOperationType.type,
        "delete": DeleteElementOperationType.type,
    },
    "automation_workflow": {
        "create": CreateAutomationWorkflowOperationType.type,
        "read": ReadAutomationWorkflowOperationType.type,
        "update": UpdateAutomationWorkflowOperationType.type,
        "delete": DeleteAutomationWorkflowOperationType.type,
    },
    "automation_node": {
        "create": CreateAutomationNodeOperationType.type,
        "read": ReadAutomationNodeOperationType.type,
        "update": UpdateAutomationNodeOperationType.type,
        "delete": DeleteAutomationNodeOperationType.type,
    },
    "workspace": {
        "read": ReadWorkspaceOperationType.type,
        "update": UpdateWorkspaceOperationType.type,
        "delete": DeleteWorkspaceOperationType.type,
    },
}

CONTROLLABLE_OPERATION_TYPES = {
    operation_type
    for component in CONTROLLABLE_OPERATIONS.values()
    for operation_type in component.values()
}
