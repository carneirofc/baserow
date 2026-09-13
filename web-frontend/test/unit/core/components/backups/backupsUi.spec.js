import MockAdapter from 'axios-mock-adapter'
import { flushPromises } from '@vue/test-utils'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import BackupScheduleForm from '@baserow/modules/core/components/backups/BackupScheduleForm'
import RemoteBackupsTab from '@baserow/modules/core/components/backups/RemoteBackupsTab'
import DataExportScheduleForm from '@baserow/modules/database/components/dataExport/DataExportScheduleForm'

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
    })
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
})
