<template>
  <div>
    <Error :error="error"></Error>
    <BackupScheduleForm
      v-if="editing"
      :schedule="editingSchedule"
      :destinations="destinations"
      :loading="saving"
      @submit="save"
      @cancel="editing = false"
    />
    <template v-else>
      <Button icon="iconoir-plus" @click="edit(null)">
        {{ $t('backupsModal.newSchedule') }}
      </Button>
      <div v-if="loading" class="loading margin-top-3"></div>
      <p v-else-if="schedules.length === 0" class="margin-top-3">
        {{ $t('backupsModal.noSchedules') }}
      </p>
      <div v-else class="export-workspace__list margin-top-3">
        <div
          v-for="schedule in schedules"
          :key="schedule.id"
          class="export-workspace__export"
        >
          <div class="export-workspace__info">
            <div>
              <div class="export-workspace__name">
                {{ schedule.name }}
                <template v-if="!schedule.is_active">
                  ({{ $t('backupsModal.inactive') }})
                </template>
              </div>
              <div class="export-workspace__detail">
                <code>{{ schedule.cron }}</code> {{ schedule.timezone }}
                <template v-if="schedule.destination">
                  ·
                  {{
                    $t('backupsModal.uploadedTo', {
                      name: schedule.destination,
                    })
                  }}
                </template>
                <template v-if="schedule.is_active">
                  · {{ $t('backupsModal.nextRun') }}
                  {{ formatDate(schedule.next_run_on) }}
                </template>
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
              :loading="runningId === schedule.id"
              :disabled="runningId !== null"
              @click="runNow(schedule)"
            >
              {{ $t('backupsModal.runNow') }}
            </Button>
            <Button
              type="secondary"
              size="small"
              icon="iconoir-edit-pencil"
              :title="$t('backupsModal.edit')"
              @click="edit(schedule)"
            ></Button>
            <Button
              type="secondary"
              size="small"
              icon="iconoir-bin"
              :title="$t('backupsModal.delete')"
              @click="remove(schedule)"
            ></Button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import moment from '@baserow/modules/core/moment'
import BackupService from '@baserow/modules/core/services/backup'
import BackupScheduleForm from '@baserow/modules/core/components/backups/BackupScheduleForm'

export default {
  name: 'BackupSchedulesTab',
  components: { BackupScheduleForm },
  mixins: [error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    destinations: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      saving: false,
      editing: false,
      editingSchedule: null,
      runningId: null,
      schedules: [],
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    formatDate(value) {
      return value ? moment(value).format('YYYY-MM-DD HH:mm') : ''
    },
    async load() {
      this.loading = true
      try {
        const { data } = await BackupService(this.$client).listSchedules(
          this.workspace.id
        )
        this.schedules = data
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
      const service = BackupService(this.$client)
      try {
        if (this.editingSchedule) {
          await service.updateSchedule(this.editingSchedule.id, values)
        } else {
          await service.createSchedule(this.workspace.id, values)
        }
        this.editing = false
        await this.load()
      } catch (error) {
        this.handleError(error)
      } finally {
        this.saving = false
      }
    },
    async runNow(schedule) {
      this.runningId = schedule.id
      this.hideError()
      try {
        const { data: job } = await BackupService(this.$client).runSchedule(
          schedule.id
        )
        await this.$store.dispatch('job/create', job)
        this.$store.dispatch('toast/info', {
          title: this.$t('backupsModal.runStartedTitle'),
          message: this.$t('backupsModal.runStartedMessage'),
        })
      } catch (error) {
        this.handleError(error)
      } finally {
        this.runningId = null
      }
    },
    async remove(schedule) {
      this.hideError()
      try {
        await BackupService(this.$client).deleteSchedule(schedule.id)
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
