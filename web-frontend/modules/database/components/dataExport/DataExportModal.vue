<template>
  <Modal ref="modal" :full-screen="false" :close-button="true">
    <h2 class="box__title">
      {{ $t('dataExportModal.title') }} {{ database.name }}
    </h2>
    <p>{{ $t('dataExportModal.description') }}</p>
    <Error :error="error"></Error>
    <div v-if="loading" class="loading margin-top-2 margin-bottom-2"></div>
    <p v-else-if="loaded && destinations.length === 0">
      {{ $t('dataExportModal.noDestinations') }}
    </p>
    <template v-else-if="loaded">
      <DataExportScheduleForm
        v-if="editing"
        :schedule="editingSchedule"
        :database="database"
        :destinations="destinations"
        :loading="saving"
        @submit="save"
        @cancel="editing = false"
      />
      <template v-else>
        <Button icon="iconoir-plus" @click="edit(null)">
          {{ $t('dataExportModal.newSchedule') }}
        </Button>
        <p v-if="schedules.length === 0" class="margin-top-3">
          {{ $t('dataExportModal.noSchedules') }}
        </p>
        <div v-else class="export-workspace__list margin-top-3">
          <div v-for="schedule in schedules" :key="schedule.id">
            <div class="export-workspace__export">
              <div class="export-workspace__info">
                <div>
                  <div class="export-workspace__name">
                    {{ schedule.name }}
                    <template v-if="!schedule.is_active">
                      ({{ $t('dataExportModal.inactive') }})
                    </template>
                  </div>
                  <div class="export-workspace__detail">
                    <code>{{ schedule.cron }}</code> {{ schedule.timezone }} ·
                    {{ schedule.destination }} ·
                    {{ tablesLabel(schedule) }}
                    <template v-if="schedule.is_active">
                      · {{ $t('dataExportModal.nextRun') }}
                      {{ formatDate(schedule.next_run_on) }}
                    </template>
                  </div>
                  <div
                    v-for="warning in schedule.warnings"
                    :key="warning"
                    class="export-workspace__detail color-warning"
                  >
                    {{ warning }}
                  </div>
                  <div
                    v-if="schedule.last_error"
                    class="export-workspace__detail color-error"
                  >
                    {{ schedule.last_error }}
                  </div>
                </div>
              </div>
              <div class="export-workspace__actions">
                <Button
                  type="secondary"
                  size="small"
                  :loading="busyId === schedule.id"
                  :disabled="busyId !== null"
                  @click="run(schedule, 'auto')"
                >
                  {{ $t('dataExportModal.runNow') }}
                </Button>
                <Button
                  type="secondary"
                  size="small"
                  :disabled="busyId !== null"
                  @click="run(schedule, 'full')"
                >
                  {{ $t('dataExportModal.runFull') }}
                </Button>
                <Button
                  type="secondary"
                  size="small"
                  icon="iconoir-list"
                  :title="$t('dataExportModal.runs')"
                  @click="toggleRuns(schedule)"
                ></Button>
                <Button
                  type="secondary"
                  size="small"
                  icon="iconoir-edit-pencil"
                  :title="$t('dataExportModal.edit')"
                  @click="edit(schedule)"
                ></Button>
                <Button
                  type="secondary"
                  size="small"
                  icon="iconoir-bin"
                  :title="$t('dataExportModal.delete')"
                  @click="remove(schedule)"
                ></Button>
              </div>
            </div>
            <div
              v-if="openRunsId === schedule.id"
              class="margin-bottom-2 margin-left-2"
            >
              <div v-if="runsLoading" class="loading"></div>
              <p v-else-if="runs.length === 0">
                {{ $t('dataExportModal.noRuns') }}
              </p>
              <table v-else class="data-export__runs">
                <thead>
                  <tr>
                    <th>{{ $t('dataExportModal.started') }}</th>
                    <th>{{ $t('dataExportModal.duration') }}</th>
                    <th>{{ $t('dataExportModal.table') }}</th>
                    <th>{{ $t('dataExportModal.mode') }}</th>
                    <th>{{ $t('dataExportModal.state') }}</th>
                    <th>{{ $t('dataExportModal.rows') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="exportRun in runs" :key="exportRun.id">
                    <td>{{ formatDate(exportRun.started_on) }}</td>
                    <td>
                      <span v-if="exportRun.finished_on">{{
                        runDuration(exportRun)
                      }}</span>
                      <span v-else class="job-duration">{{
                        $t('dataExportModal.runInProgress')
                      }}</span>
                    </td>
                    <td>{{ tableName(exportRun.table_id) }}</td>
                    <td>{{ exportRun.mode }}</td>
                    <td :title="exportRun.error || exportRun.object_prefix">
                      {{ exportRun.state }}
                    </td>
                    <td>{{ exportRun.row_count }}</td>
                  </tr>
                </tbody>
              </table>
              <Button
                type="secondary"
                size="small"
                class="margin-top-1"
                :loading="resetting"
                @click="resetState(schedule)"
              >
                {{ $t('dataExportModal.resetState') }}
              </Button>
            </div>
          </div>
        </div>
      </template>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import moment from '@baserow/modules/core/moment'
import { elapsedMs, formatElapsedMs } from '@baserow/modules/core/utils/job'
import BackupService from '@baserow/modules/core/services/backup'
import DataExportService from '@baserow/modules/database/services/dataExport'
import DataExportScheduleForm from '@baserow/modules/database/components/dataExport/DataExportScheduleForm'

export default {
  name: 'DataExportModal',
  components: { DataExportScheduleForm },
  mixins: [modal, error],
  props: {
    database: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      loaded: false,
      saving: false,
      editing: false,
      editingSchedule: null,
      busyId: null,
      resetting: false,
      openRunsId: null,
      runsLoading: false,
      runs: [],
      destinations: [],
      schedules: [],
    }
  },
  methods: {
    show(...args) {
      modal.methods.show.bind(this)(...args)
      this.editing = false
      this.openRunsId = null
      this.load()
    },
    formatDate(value) {
      return value ? moment(value).format('YYYY-MM-DD HH:mm') : ''
    },
    runDuration(exportRun) {
      return formatElapsedMs(
        elapsedMs(exportRun.started_on, exportRun.finished_on)
      )
    },
    tableName(tableId) {
      const table = (this.database.tables || []).find(
        (item) => item.id === tableId
      )
      return table ? table.name : tableId
    },
    tablesLabel(schedule) {
      if (schedule.table_ids === null) {
        return this.$t('dataExportModal.allTables')
      }
      return schedule.table_ids.map((id) => this.tableName(id)).join(', ')
    },
    async load() {
      this.loading = true
      this.hideError()
      try {
        const [{ data: destinations }, { data: schedules }] = await Promise.all(
          [
            BackupService(this.$client).listDestinations(),
            DataExportService(this.$client).listSchedules(this.workspace.id),
          ]
        )
        this.destinations = destinations.filter((destination) =>
          destination.purposes.includes('datalake')
        )
        this.schedules = schedules.filter(
          (schedule) => schedule.database === this.database.id
        )
        this.loaded = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
    edit(schedule) {
      this.hideError()
      this.editingSchedule = schedule
      this.editing = true
    },
    async save(values) {
      this.saving = true
      this.hideError()
      const service = DataExportService(this.$client)
      try {
        if (this.editingSchedule) {
          await service.updateSchedule(this.editingSchedule.id, values)
        } else {
          await service.createSchedule(this.workspace.id, {
            ...values,
            database_id: this.database.id,
          })
        }
        this.editing = false
        await this.load()
      } catch (error) {
        this.handleError(error)
      } finally {
        this.saving = false
      }
    },
    async run(schedule, mode) {
      this.busyId = schedule.id
      this.hideError()
      try {
        await DataExportService(this.$client).runSchedule(schedule.id, mode)
        this.$store.dispatch('toast/info', {
          title: this.$t('dataExportModal.runQueuedTitle'),
          message: this.$t('dataExportModal.runQueuedMessage'),
        })
      } catch (error) {
        this.handleError(error)
      } finally {
        this.busyId = null
      }
    },
    async toggleRuns(schedule) {
      if (this.openRunsId === schedule.id) {
        this.openRunsId = null
        return
      }
      this.openRunsId = schedule.id
      this.runsLoading = true
      try {
        const { data } = await DataExportService(this.$client).listRuns(
          schedule.id
        )
        this.runs = data
      } catch (error) {
        this.handleError(error)
      } finally {
        this.runsLoading = false
      }
    },
    async resetState(schedule) {
      this.resetting = true
      this.hideError()
      try {
        await DataExportService(this.$client).resetState(schedule.id)
        this.$store.dispatch('toast/info', {
          title: this.$t('dataExportModal.resetStateTitle'),
          message: this.$t('dataExportModal.resetStateMessage'),
        })
      } catch (error) {
        this.handleError(error)
      } finally {
        this.resetting = false
      }
    },
    async remove(schedule) {
      this.hideError()
      try {
        await DataExportService(this.$client).deleteSchedule(schedule.id)
        this.schedules = this.schedules.filter(
          (item) => item.id !== schedule.id
        )
      } catch (error) {
        this.handleError(error)
      }
    },
  },
}
</script>
