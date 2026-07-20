from baserow.core.registries import operation_type_registry
from baserow.core.roles.controllable_operations import (
    CONTROLLABLE_OPERATION_TYPES,
    CONTROLLABLE_OPERATIONS,
)


def test_controllable_operation_types_are_all_registered():
    for operation_type in CONTROLLABLE_OPERATION_TYPES:
        # Raises if the operation type isn't registered.
        operation_type_registry.get(operation_type)


def test_controllable_operation_types_is_the_flattened_component_map():
    expected = {
        operation_type
        for component in CONTROLLABLE_OPERATIONS.values()
        for operation_type in component.values()
    }

    assert CONTROLLABLE_OPERATION_TYPES == expected
