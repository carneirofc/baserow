import { TestApp } from '@baserow/test/helpers/testApp'
import ImportFileModal from '@baserow/modules/database/components/table/ImportFileModal'
import TableService from '@baserow/modules/database/services/table'

vi.mock('@baserow/modules/database/services/table', () => ({
  default: vi.fn(),
}))

describe('ImportFileModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.clearAllMocks()
  })

  const database = { id: 1, name: 'Cars', workspace: { id: 10 } }
  const table = { id: 5, name: 'Contacts' }

  const makeField = (id, name, type) => ({
    id,
    name,
    type,
    primary: id === 100,
    order: id,
    _: { type: testApp.getRegistry().get('field', type) },
  })

  const mountModal = async () => {
    const fields = [
      makeField(100, 'Name', 'text'),
      makeField(101, 'Amount', 'number'),
    ]
    const wrapper = await testApp.mount(ImportFileModal, {
      props: { database, table, fields },
    })
    return { wrapper, fields }
  }

  /**
   * Puts the component in the state it reaches once a two column file has been
   * parsed and both columns mapped, which is what the strict modes require.
   */
  const loadFile = async (wrapper, mapping) => {
    await wrapper.setData({
      importer: 'excel',
      header: ['Name', 'Amount'],
      previewData: [['Ada', '1']],
      dataLoaded: true,
      mapping,
    })
  }

  test('appending stays possible with a partial mapping', async () => {
    const { wrapper } = await mountModal()
    await loadFile(wrapper, { 0: 100, 1: 0 })

    expect(wrapper.vm.isStrictMode).toBe(false)
    expect(wrapper.vm.strictMappingProblems).toEqual([])
    expect(wrapper.vm.canBeSubmitted).toBe(true)
  })

  test('a strict mode reports an unmapped file column', async () => {
    const { wrapper } = await mountModal()
    await wrapper.setData({ mode: 'upsert', upsertField: 100 })
    await loadFile(wrapper, { 0: 100, 1: 0 })

    expect(wrapper.vm.unmappedFileColumns).toEqual(['Amount'])
    expect(wrapper.vm.uncoveredFields.map((f) => f.name)).toEqual(['Amount'])
    expect(wrapper.vm.strictMappingProblems).toHaveLength(2)
    expect(wrapper.vm.canBeSubmitted).toBe(false)
  })

  test('a strict mode is satisfied by a total mapping', async () => {
    const { wrapper } = await mountModal()
    await wrapper.setData({ mode: 'upsert', upsertField: 100 })
    await loadFile(wrapper, { 0: 100, 1: 101 })

    expect(wrapper.vm.strictMappingProblems).toEqual([])
    expect(wrapper.vm.canBeSubmitted).toBe(true)
  })

  test('upsert cannot be submitted without a match field', async () => {
    const { wrapper } = await mountModal()
    await wrapper.setData({ mode: 'upsert' })
    await loadFile(wrapper, { 0: 100, 1: 101 })

    expect(wrapper.vm.canBeSubmitted).toBe(false)

    await wrapper.setData({ upsertField: 100 })
    expect(wrapper.vm.canBeSubmitted).toBe(true)
  })

  test('replace requires the confirmation to be ticked', async () => {
    const { wrapper } = await mountModal()
    await wrapper.setData({ mode: 'replace' })
    await loadFile(wrapper, { 0: 100, 1: 101 })

    expect(wrapper.vm.canBeSubmitted).toBe(false)

    await wrapper.setData({ replaceConfirmed: true })
    expect(wrapper.vm.canBeSubmitted).toBe(true)
  })

  test('switching mode clears a previous replace confirmation', async () => {
    const { wrapper } = await mountModal()
    await wrapper.setData({ mode: 'replace', replaceConfirmed: true })

    wrapper.vm.onModeClick({ value: 'append', allowed: true })

    expect(wrapper.vm.mode).toBe('append')
    expect(wrapper.vm.replaceConfirmed).toBe(false)
  })

  test('a mode the user may not use cannot be selected', async () => {
    const { wrapper } = await mountModal()

    wrapper.vm.onModeClick({ value: 'replace', allowed: false })

    expect(wrapper.vm.mode).toBe('append')
  })

  test('a strict import sends the mode and the full column mapping', async () => {
    const importData = vi
      .fn()
      .mockResolvedValue({ data: { id: 1, type: 'file_import' } })
    TableService.mockReturnValue({ importData })

    const { wrapper } = await mountModal()
    await wrapper.setData({ mode: 'replace', replaceConfirmed: true })
    await loadFile(wrapper, { 0: 100, 1: 101 })
    await wrapper.setData({ getData: () => [['Ada', '1']] })
    wrapper.vm.createAndMonitorJob = vi.fn()

    await wrapper.vm.submitted()

    expect(importData).toHaveBeenCalled()
    const [tableId, data, , configuration, metadata] = importData.mock.calls[0]
    expect(tableId).toBe(table.id)
    expect(data).toHaveLength(1)
    expect(configuration.file_header).toEqual(['Name', 'Amount'])
    expect(configuration.field_mapping).toEqual([100, 101])
    expect(metadata.mode).toBe('replace')
  })

  test('an append sends no column mapping', async () => {
    const importData = vi
      .fn()
      .mockResolvedValue({ data: { id: 1, type: 'file_import' } })
    TableService.mockReturnValue({ importData })

    const { wrapper } = await mountModal()
    await loadFile(wrapper, { 0: 100, 1: 0 })
    await wrapper.setData({ getData: () => [['Ada', '1']] })
    wrapper.vm.createAndMonitorJob = vi.fn()

    await wrapper.vm.submitted()

    const [, , , configuration, metadata] = importData.mock.calls[0]
    expect(metadata.mode).toBe('append')
    expect(configuration?.file_header).toBeUndefined()
  })
})
