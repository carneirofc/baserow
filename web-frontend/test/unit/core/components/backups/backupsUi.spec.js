import MockAdapter from 'axios-mock-adapter'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import BackupScheduleForm from '@baserow/modules/core/components/backups/BackupScheduleForm'
import RemoteBackupsTab from '@baserow/modules/core/components/backups/RemoteBackupsTab'
import BackupsTab from '@baserow/modules/core/components/backups/BackupsTab'
import BackupSchedulesTab from '@baserow/modules/core/components/backups/BackupSchedulesTab'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import DataExportScheduleForm from '@baserow/modules/database/components/dataExport/DataExportScheduleForm'
import DataExportModal from '@baserow/modules/database/components/dataExport/DataExportModal'

const BACKUP = {
  id: 4,
  resource_id: 'r4',
  created_on: '2026-01-01T03:00:00+00:00',
  exported_file_name: 'backup.zip',
  download_url: '/download/backup.zip',
  destination: '',
}

function deferred() {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}

// A request that never settles, so starting a restore does not go on to poll a job.
function pending() {
  return new Promise(() => {})
}

function remoteBackup(key) {
  return {
    key,
    created_on: '2026-01-01T03:00:00+00:00',
    size: 2048,
    only_structure: false,
    instance_id: 'this-instance',
    schedule_id: null,
    applications: [{ id: 5, name: key, type: 'database' }],
  }
}

describe('backups and datalake export UI', () => {
  let mock = null
  let wrapper = null

  beforeEach(() => {
    mock = new MockAdapter(useNuxtApp().$client, {
      onNoMatch: 'throwException',
    })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
    mock.restore()
  })

  test('the backup schedule form emits normalized values', async () => {
    wrapper = await mountSuspended(BackupScheduleForm, {
      props: { destinations: [{ name: 'offsite', type: 's3' }] },
    })

    wrapper.vm.submit()
    expect(wrapper.emitted('submit')).toBeUndefined()

    wrapper.vm.values.name = '  Nightly  '
    wrapper.vm.values.destination = 'offsite'
    wrapper.vm.values.keep_last = '7'
    wrapper.vm.values.keep_days = ''
    wrapper.vm.submit()

    expect(wrapper.emitted('submit')[0][0]).toEqual({
      name: 'Nightly',
      cron: '0 3 * * *',
      timezone: 'UTC',
      destination: 'offsite',
      keep_last: 7,
      keep_days: null,
      only_structure: false,
      is_active: true,
      // Null rather than absent, so editing a scoped schedule back to the whole
      // workspace clears its previous selection.
      application_ids: null,
    })
  })

  test('the backup schedule form scopes to the selected applications', async () => {
    wrapper = await mountSuspended(BackupScheduleForm, {
      props: {
        destinations: [{ name: 'offsite', type: 's3' }],
        schedule: {
          name: 'Nightly',
          cron: '0 3 * * *',
          application_ids: [5, 9],
        },
      },
    })

    // An existing schedule that already names applications opens with the scope
    // enabled and those applications selected.
    expect(wrapper.vm.onlySelectedApplications).toBe(true)
    expect(wrapper.vm.selectedApplicationIds).toEqual([5, 9])

    wrapper.vm.submit()
    expect(wrapper.emitted('submit')[0][0].application_ids).toEqual([5, 9])

    wrapper.vm.onlySelectedApplications = false
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')[1][0].application_ids).toBeNull()
  })

  test('the datalake export form requires tables when not exporting all', async () => {
    wrapper = await mountSuspended(DataExportScheduleForm, {
      props: {
        database: {
          id: 1,
          name: 'Sales',
          tables: [
            { id: 10, name: 'Orders' },
            { id: 11, name: 'Customers' },
          ],
        },
        destinations: [{ name: 'lake', type: 's3' }],
      },
    })

    wrapper.vm.values.name = 'Hourly'
    wrapper.vm.allTables = false
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')).toBeUndefined()

    wrapper.vm.tableSelection[11] = true
    wrapper.vm.submit()

    const values = wrapper.emitted('submit')[0][0]
    expect(values.destination).toBe('lake')
    expect(values.table_ids).toEqual([11])
    expect(values.full_every_n).toBe(24)
    expect(values.column_naming).toBe('field_id')
  })

  test('the external storage tab lists backups of the destination', async () => {
    mock.onGet('/backups/destinations/offsite/workspace/1/').reply(200, {
      results: [
        {
          key: 'backups/workspace=1/20260101T030000Z_abc.zip',
          created_on: '2026-01-01T03:00:00+00:00',
          size: 2048,
          sha256: 'x',
          only_structure: false,
          instance_id: 'other-instance',
          baserow_version: '0.7.0',
          schedule_id: 3,
          workspace: { id: 1, name: 'Acme' },
          applications: [{ id: 5, name: 'Sales', type: 'database' }],
        },
      ],
    })

    wrapper = await mountSuspended(RemoteBackupsTab, {
      props: {
        workspace: { id: 1, name: 'Acme' },
        destinations: [
          { name: 'offsite', type: 'azure', purposes: ['backup'] },
        ],
      },
    })
    await flushPromises()

    // Translations are not loaded in unit tests, so only assert on the data itself.
    expect(wrapper.text()).toContain('2026-01-01 03:00')
    expect(wrapper.text()).toContain('Sales')
    expect(wrapper.text()).toContain('2.0 KB')
  })

  test('the backup schedule form rejects invalid retention instead of keeping all', async () => {
    wrapper = await mountSuspended(BackupScheduleForm, {
      props: { destinations: [{ name: 'offsite', type: 's3' }] },
    })
    wrapper.vm.values.name = 'Nightly'

    for (const invalid of ['0', '-3', '1.5', 'abc', 0, -1]) {
      wrapper.vm.values.keep_last = invalid
      wrapper.vm.submit()
      expect(wrapper.emitted('submit')).toBeUndefined()
    }
    wrapper.vm.values.keep_last = ''
    wrapper.vm.values.keep_days = '0'
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')).toBeUndefined()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('backupsModal.retentionInvalid')

    wrapper.vm.values.keep_days = 30
    wrapper.vm.submit()
    const values = wrapper.emitted('submit')[0][0]
    expect(values.keep_last).toBeNull()
    expect(values.keep_days).toBe(30)
  })

  test('the backup schedule form requires replacing a removed destination', async () => {
    wrapper = await mountSuspended(BackupScheduleForm, {
      props: {
        destinations: [{ name: 'offsite', type: 's3' }],
        schedule: { name: 'Nightly', cron: '0 3 * * *', destination: 'gone' },
      },
    })

    // The stale name stays visible rather than rendering a blank dropdown.
    expect(wrapper.vm.destinationUnavailable).toBe(true)
    expect(wrapper.text()).toContain('backupsModal.unavailableDestinationError')
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')).toBeUndefined()

    // Keeping the backups on the instance is a valid choice.
    wrapper.vm.values.destination = ''
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')[0][0].destination).toBe('')
  })

  test('the datalake export form validates full exports like the backend', async () => {
    wrapper = await mountSuspended(DataExportScheduleForm, {
      props: {
        database: { id: 1, name: 'Sales', tables: [] },
        destinations: [{ name: 'lake', type: 's3' }],
      },
    })
    wrapper.vm.values.name = 'Hourly'

    for (const invalid of ['', '-1', '2.5', 'abc', -1]) {
      wrapper.vm.values.full_every_n = invalid
      wrapper.vm.submit()
      expect(wrapper.emitted('submit')).toBeUndefined()
    }

    // Zero is allowed: it only exports fully when required.
    wrapper.vm.values.full_every_n = '0'
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')[0][0].full_every_n).toBe(0)
  })

  test('the datalake export form requires replacing a removed storage', async () => {
    wrapper = await mountSuspended(DataExportScheduleForm, {
      props: {
        database: { id: 1, name: 'Sales', tables: [] },
        destinations: [{ name: 'lake', type: 's3' }],
        schedule: { name: 'Hourly', cron: '0 * * * *', destination: 'gone' },
      },
    })

    wrapper.vm.submit()
    expect(wrapper.emitted('submit')).toBeUndefined()
    wrapper.vm.values.destination = 'lake'
    wrapper.vm.submit()
    expect(wrapper.emitted('submit')[0][0].destination).toBe('lake')
  })

  test('deleting and restoring a backup waits for confirmation', async () => {
    const service = {
      listBackups: vi.fn().mockResolvedValue({ data: { results: [BACKUP] } }),
      deleteBackup: vi.fn().mockResolvedValue({}),
      restoreBackup: vi.fn(pending),
    }
    wrapper = await mountSuspended(BackupsTab, {
      props: {
        workspace: { id: 1, name: 'Acme' },
        destinations: [],
        service: () => service,
      },
    })
    await flushPromises()
    const confirmModal = wrapper.findComponent(ConfirmModal)

    wrapper.vm.remove(BACKUP)
    expect(service.deleteBackup).not.toHaveBeenCalled()
    confirmModal.vm.cancel()
    expect(service.deleteBackup).not.toHaveBeenCalled()

    wrapper.vm.remove(BACKUP)
    await confirmModal.vm.confirm()
    expect(service.deleteBackup).toHaveBeenCalledWith(1, 'r4')
    expect(wrapper.vm.backups).toEqual([])

    wrapper.vm.restore(BACKUP)
    expect(service.restoreBackup).not.toHaveBeenCalled()
    // The restore warns that the applications are installed as new ones.
    expect(confirmModal.vm.message).toBe('backupsModal.confirmRestoreMessage')
    confirmModal.vm.confirm()
    expect(service.restoreBackup).toHaveBeenCalledWith(1, 'r4')
  })

  test('deleting a backup schedule waits for confirmation', async () => {
    const schedule = { id: 7, name: 'Nightly', cron: '0 3 * * *' }
    const service = {
      listSchedules: vi.fn().mockResolvedValue({ data: [schedule] }),
      deleteSchedule: vi.fn().mockResolvedValue({}),
    }
    wrapper = await mountSuspended(BackupSchedulesTab, {
      props: {
        workspace: { id: 1, name: 'Acme' },
        destinations: [],
        service: () => service,
      },
    })
    await flushPromises()

    wrapper.vm.remove(schedule)
    expect(service.deleteSchedule).not.toHaveBeenCalled()
    await wrapper.findComponent(ConfirmModal).vm.confirm()
    expect(service.deleteSchedule).toHaveBeenCalledWith(7)
    expect(wrapper.vm.schedules).toEqual([])
  })

  test('the external storage tab confirms a restore and ignores stale lists', async () => {
    const slowA = deferred()
    const service = {
      listRemoteBackups: vi.fn((destination) =>
        destination === 'a'
          ? slowA.promise
          : Promise.resolve({ data: { results: [remoteBackup('b-key')] } })
      ),
      restoreRemoteBackup: vi.fn(pending),
    }
    wrapper = await mountSuspended(RemoteBackupsTab, {
      props: {
        workspace: { id: 1, name: 'Acme' },
        destinations: [
          { name: 'a', type: 's3', purposes: ['backup'] },
          { name: 'b', type: 's3', purposes: ['backup'] },
        ],
        service: () => service,
      },
    })

    // Switch to b while the list of a is still loading, then let a answer late.
    wrapper.vm.selectDestination('b')
    await flushPromises()
    slowA.resolve({ data: { results: [remoteBackup('a-key')] } })
    await flushPromises()

    expect(wrapper.vm.destination).toBe('b')
    expect(wrapper.vm.backups.map((backup) => backup.key)).toEqual(['b-key'])
    expect(wrapper.vm.loading).toBe(false)

    wrapper.vm.restore(wrapper.vm.backups[0])
    expect(service.restoreRemoteBackup).not.toHaveBeenCalled()
    wrapper.findComponent(ConfirmModal).vm.confirm()
    expect(service.restoreRemoteBackup).toHaveBeenCalledWith('b', 1, {
      key: 'b-key',
    })
  })

  test('the external storage tab retries a destination after a failure', async () => {
    const url = '/backups/destinations/a/workspace/1/'
    mock
      .onGet(url)
      .replyOnce(500)
      .onGet(url)
      .reply(200, { results: [remoteBackup('a-key')] })
    wrapper = await mountSuspended(RemoteBackupsTab, {
      props: {
        workspace: { id: 1, name: 'Acme' },
        destinations: [{ name: 'a', type: 's3', purposes: ['backup'] }],
      },
    })
    await flushPromises()
    expect(wrapper.vm.backups).toEqual([])
    expect(wrapper.vm.error.visible).toBe(true)

    wrapper.vm.selectDestination('a')
    await flushPromises()
    expect(mock.history.get).toHaveLength(2)
    expect(wrapper.vm.backups.map((backup) => backup.key)).toEqual(['a-key'])
  })

  test('the datalake export modal lists schedules without any storage', async () => {
    mock.onGet('/data-destinations/').reply(200, [])
    mock.onGet('/database/data-export/schedules/workspace/1/').reply(200, [
      {
        id: 3,
        name: 'Hourly lake',
        database: 2,
        cron: '0 * * * *',
        timezone: 'UTC',
        destination: 'removed',
        table_ids: null,
        is_active: false,
        warnings: [],
      },
    ])
    mock.onDelete('/database/data-export/schedules/3/').reply(204)

    wrapper = await mountSuspended(DataExportModal, {
      props: {
        database: { id: 2, name: 'Sales', tables: [] },
        workspace: { id: 1, name: 'Acme' },
      },
      // Render the modal in place instead of teleporting it to the body.
      global: { stubs: { teleport: true } },
    })
    wrapper.vm.show()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Hourly lake')
    expect(text).toContain('dataExportModal.noDestinations')
    expect(text).not.toContain('dataExportModal.newSchedule')

    wrapper.vm.remove(wrapper.vm.schedules[0])
    await flushPromises()
    expect(mock.history.delete).toHaveLength(0)
    await wrapper.findComponent(ConfirmModal).vm.confirm()
    expect(mock.history.delete).toHaveLength(1)
    expect(wrapper.vm.schedules).toEqual([])
  })
})
