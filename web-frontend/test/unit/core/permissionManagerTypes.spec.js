import { GranularRolePermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

describe('GranularRolePermissionManagerType', () => {
  const manager = new GranularRolePermissionManagerType({ app: {} })
  const controllable = [
    'database.table.create_row',
    'database.table.delete_row',
  ]

  test('allows a controllable operation the role grants', () => {
    const permissions = {
      controllable_operations: controllable,
      allowed_operations: ['database.table.create_row'],
    }

    expect(
      manager.hasPermission(permissions, 'database.table.create_row', null, 1)
    ).toBe(true)
  })

  test('denies a controllable operation the role does not grant', () => {
    const permissions = {
      controllable_operations: controllable,
      allowed_operations: ['database.table.create_row'],
    }

    expect(
      manager.hasPermission(permissions, 'database.table.delete_row', null, 1)
    ).toBe(false)
  })

  test('defers operations the role cannot control', () => {
    const permissions = {
      controllable_operations: controllable,
      allowed_operations: [],
    }

    expect(
      manager.hasPermission(permissions, 'workspace.read', null, 1)
    ).toBeNull()
  })

  test('defers when the member has no role or is not a member', () => {
    const noRole = {
      controllable_operations: controllable,
      allowed_operations: null,
    }

    expect(
      manager.hasPermission(noRole, 'database.table.delete_row', null, 1)
    ).toBeNull()
    expect(
      manager.hasPermission(null, 'database.table.delete_row', null, 1)
    ).toBeNull()
  })
})
