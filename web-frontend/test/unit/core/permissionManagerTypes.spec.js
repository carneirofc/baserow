import { GranularRolePermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

describe('GranularRolePermissionManagerType', () => {
  const manager = new GranularRolePermissionManagerType({})
  const controllable = [
    'database.table.import_rows',
    'database.table.upsert_rows',
    'database.table.replace_rows',
  ]

  const check = (allowed, operation) =>
    manager.hasPermission(
      { controllable_operations: controllable, allowed_operations: allowed },
      operation,
      null,
      1
    )

  test('abstains when the user has no custom role', () => {
    // `allowed_operations` is null for an admin or a member without a role, who
    // keep whatever the other managers decide.
    expect(check(null, 'database.table.replace_rows')).toBeUndefined()
  })

  test('abstains for an operation that is not controllable', () => {
    expect(check([], 'database.table.read')).toBeUndefined()
  })

  test('grants a controllable operation the role lists', () => {
    expect(
      check(['database.table.import_rows'], 'database.table.import_rows')
    ).toBe(true)
  })

  test('denies a controllable operation the role omits', () => {
    // A role may grant a plain append without also granting the destructive
    // replace, which is exactly what gates the import modes.
    expect(
      check(['database.table.import_rows'], 'database.table.replace_rows')
    ).toBe(false)
  })
})
