<template>
  <div>
    <Error :error="error"></Error>
    <p v-if="destinations.length === 0">
      {{ $t('backupsModal.noBackupDestinations') }}
    </p>
    <template v-else>
      <div class="row">
        <div class="col col-6">
          <FormGroup
            small-label
            :label="$t('backupsModal.destination')"
            class="margin-bottom-2"
          >
            <Dropdown
              v-model="destination"
              :disabled="busy"
              @input="load"
              @update:model-value="load"
            >
              <DropdownItem
                v-for="item in destinations"
                :key="item.name"
                :name="item.name"
                :value="item.name"
              ></DropdownItem>
            </Dropdown>
          </FormGroup>
        </div>
        <div v-if="isStaff" class="col col-6">
          <FormGroup
            small-label
            :label="$t('backupsModal.signingKey')"
            :helper-text="$t('backupsModal.trustPublicKeyHelp')"
            class="margin-bottom-2"
          >
            <Checkbox v-model="trustPublicKey" :disabled="busy">
              {{ $t('backupsModal.trustPublicKey') }}
            </Checkbox>
          </FormGroup>
        </div>
      </div>
      <ProgressBar
        v-if="jobIsRunning"
        class="margin-bottom-2"
        :value="job.progress_percentage || 0"
        :status="jobHumanReadableState"
      />
      <div v-if="loading" class="loading margin-top-2"></div>
      <p v-else-if="backups.length === 0" class="margin-top-2">
        {{ $t('backupsModal.noRemoteBackups') }}
      </p>
      <div v-else class="export-workspace__list margin-top-2">
        <div
          v-for="backup in backups"
          :key="backup.key"
          class="export-workspace__export"
        >
          <div class="export-workspace__info">
            <div>
              <div class="export-workspace__name">
                {{ formatDate(backup.created_on) }} ·
                {{ applicationNames(backup) }}
              </div>
              <div class="export-workspace__detail">
                {{ formatSize(backup.size) }}
                <template v-if="backup.only_structure">
                  · {{ $t('backupsModal.structureOnly') }}
                </template>
                <template v-if="backup.schedule_id">
                  · {{ $t('backupsModal.scheduled') }}
                </template>
                · {{ $t('backupsModal.instance', { id: backup.instance_id }) }}
              </div>
            </div>
          </div>
          <div class="export-workspace__actions">
            <Button
              type="secondary"
              size="small"
              :loading="busy && restoringKey === backup.key"
              :disabled="busy"
              @click="restore(backup)"
            >
              {{ $t('backupsModal.restore') }}
            </Button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import job from '@baserow/modules/core/mixins/job'
import moment from '@baserow/modules/core/moment'
import BackupService from '@baserow/modules/core/services/backup'
import { restoredApplicationsFinished } from '@baserow/modules/core/components/backups/BackupsTab'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

export default {
  name: 'RemoteBackupsTab',
  mixins: [error, job],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    destinations: {
      type: Array,
      required: true,
    },
    service: {
      type: Function,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      loading: false,
      starting: false,
      destination: this.destinations[0]?.name || '',
      loadedDestination: null,
      trustPublicKey: false,
      restoringKey: null,
      backups: [],
    }
  },
  computed: {
    resolvedService() {
      return (this.service || BackupService)(this.$client)
    },
    busy() {
      return this.starting || this.jobIsRunning
    },
    isStaff() {
      return this.$store.getters['auth/isStaff']
    },
  },
  mounted() {
    this.load()
  },
  methods: {
    formatDate(value) {
      return moment(value).format('YYYY-MM-DD HH:mm')
    },
    formatSize(bytes) {
      const kilobytes = (bytes || 0) / 1024
      if (kilobytes < 1024) {
        return `${kilobytes.toFixed(1)} KB`
      }
      return `${(kilobytes / 1024).toFixed(1)} MB`
    },
    applicationNames(backup) {
      return (backup.applications || [])
        .map((application) => application.name)
        .join(', ')
    },
    async load() {
      // The dropdown can report the same selection through two events.
      if (!this.destination || this.loadedDestination === this.destination) {
        return
      }
      this.loadedDestination = this.destination
      this.loading = true
      this.hideError()
      try {
        const { data } = await this.resolvedService.listRemoteBackups(
          this.destination,
          this.workspace.id
        )
        this.backups = data.results || []
      } catch (error) {
        this.backups = []
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
    async restore(backup) {
      this.starting = true
      this.restoringKey = backup.key
      this.hideError()
      try {
        const values = { key: backup.key }
        if (this.isStaff && this.trustPublicKey) {
          values.trust_public_key = true
        }
        const { data } = await this.resolvedService.restoreRemoteBackup(
          this.destination,
          this.workspace.id,
          values
        )
        await this.createAndMonitorJob(data)
      } catch (error) {
        this.restoringKey = null
        this.handleError(error, 'backup', {
          ERROR_UNTRUSTED_PUBLIC_KEY: new ResponseErrorMessage(
            this.$t('backupsModal.untrustedKeyTitle'),
            this.$t('backupsModal.untrustedKeyMessage')
          ),
        })
      } finally {
        this.starting = false
      }
    },
    async onJobFinished() {
      this.restoringKey = null
      await restoredApplicationsFinished(this, this.job)
    },
    onJobFailed() {
      this.restoringKey = null
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },
  },
}
</script>
