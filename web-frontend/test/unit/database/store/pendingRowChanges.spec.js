import pendingRowChanges from '@baserow/modules/database/store/pendingRowChanges'
import rowModal from '@baserow/modules/database/store/rowModal'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('pendingRowChanges store', () => {
  let testApp = null
  let store = null
  const table = { id: 1, require_edit_confirmation: true }
  const field = { id: 10, type: 'text' }
  const otherField = { id: 11, type: 'text' }

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        pendingRowChanges,
        rowModal,
      },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('stage keeps the first old value and counts changed cells', async () => {
    const row = { id: 5, field_10: 'a', field_11: 'x' }
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row,
      field,
      value: 'b',
      oldValue: 'a',
    })
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row,
      field,
      value: 'c',
      oldValue: 'b',
    })
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row,
      field: otherField,
      value: 'y',
      oldValue: 'x',
    })

    expect(store.getters['pendingRowChanges/count'](table.id)).toBe(2)
    expect(store.getters['pendingRowChanges/hasPending'](table.id)).toBe(true)
    expect(
      store.getters['pendingRowChanges/isCellPending'](table.id, row.id, 10)
    ).toBe(true)
    expect(
      store.state.pendingRowChanges.tables[table.id][row.id].fields[10]
    ).toMatchObject({ value: 'c', oldValue: 'a' })
  })

  test('staging the original value again removes the pending change', async () => {
    const row = { id: 5, field_10: 'a' }
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row,
      field,
      value: 'b',
      oldValue: 'a',
    })
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row,
      field,
      value: 'a',
      oldValue: 'b',
    })

    expect(store.getters['pendingRowChanges/count'](table.id)).toBe(0)
    expect(store.getters['pendingRowChanges/hasPending'](table.id)).toBe(false)
  })

  test('forgetRow drops the changes of a deleted row', async () => {
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row: { id: 5, field_10: 'a' },
      field,
      value: 'b',
      oldValue: 'a',
    })
    await store.dispatch('pendingRowChanges/stage', {
      table,
      row: { id: 6, field_10: 'a' },
      field,
      value: 'b',
      oldValue: 'a',
    })

    await store.dispatch('pendingRowChanges/forgetRow', {
      tableId: table.id,
      rowId: 5,
    })

    expect(store.getters['pendingRowChanges/count'](table.id)).toBe(1)
    expect(store.getters['pendingRowChanges/isRowPending'](table.id, 5)).toBe(
      false
    )
  })

  test('confirm resolves with the answer of the mounted host', async () => {
    await store.dispatch('pendingRowChanges/registerConfirmationHost')

    const confirmed = store.dispatch('pendingRowChanges/confirm', {
      title: 'Delete row',
      message: 'Sure?',
      danger: true,
    })
    expect(store.getters['pendingRowChanges/getConfirmation']).toMatchObject({
      title: 'Delete row',
      danger: true,
    })
    await store.dispatch('pendingRowChanges/resolveConfirmation', true)
    expect(await confirmed).toBe(true)
    expect(store.getters['pendingRowChanges/getConfirmation']).toBe(null)

    const cancelled = store.dispatch('pendingRowChanges/confirm', {
      title: 'Delete row',
      message: 'Sure?',
    })
    await store.dispatch('pendingRowChanges/resolveConfirmation', false)
    expect(await cancelled).toBe(false)
  })

  test('unmounting the last host cancels an open confirmation', async () => {
    await store.dispatch('pendingRowChanges/registerConfirmationHost')
    const pending = store.dispatch('pendingRowChanges/confirm', {
      title: 'Move row',
      message: 'Sure?',
    })
    await store.dispatch('pendingRowChanges/unregisterConfirmationHost')
    expect(await pending).toBe(false)
  })
})
