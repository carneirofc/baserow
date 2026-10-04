<template>
  <div>
    <Error :error="error"></Error>
    <p v-if="destinations.length === 0">
      {{
        isStaff
          ? $t('backupsModal.noBackupDestinationsStaff')
          : $t('backupsModal.noBackupDestinations')
      }}
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
              :model-value="destination"
              :disabled="busy"
              @update:model-value="selectDestination"
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
      <template v-if="jobIsRunning">
        <ProgressBar
          :value="job.progress_percentage || 0"
          :status="jobHumanReadableState"
        />
        <JobDuration :job="job" class="margin-bottom-2" />
      </template>
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
    <ConfirmModal ref="confirmModal" />
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import job from '@baserow/modules/core/mixins/job'
import backupJobMemory from '@baserow/modules/core/mixins/backupJobMemory'
import moment from '@baserow/modules/core/moment'
import BackupService from '@baserow/modules/core/services/backup'
import { restoredApplicationsFinished } from '@baserow/modules/core/utils/backups'
import { formatFileSize } from '@baserow/modules/core/utils/file'
import JobDuration from '@baserow/modules/core/components/job/JobDuration'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'

export default {
  name: 'RemoteBackupsTab',
  components: { JobDuration, ConfirmModal },
  mixins: [error, job, backupJobMemory],
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
      loadRequest: 0,
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
    const remembered = this.resumeJob('remote')
    if (remembered) {
      this.restoringKey = remembered.restoringKey
    }
    this.load()
  },
  methods: {
    formatDate(value) {
      return moment(value).format('L LT')
    },
    formatSize(bytes) {
      return formatFileSize(this.$t, this.$i18n.locale, bytes || 0)
    },
    applicationNames(backup) {
      return (backup.applications || [])
        .map((application) => application.name)
        .join(', ')
    },
    selectDestination(value) {
      this.destination = value
      this.load()
    },
    async load() {
      if (!this.destination || this.loadedDestination === this.destination) {
        return
      }
      // Only the response for the destination that is still selected may fill
      // the list, otherwise a slow answer for a previous destination would show
      // its backups, and restore their keys, under the current one.
      const destination = this.destination
      const request = ++this.loadRequest
      this.loadedDestination = destination
      this.loading = true
      this.hideError()
      try {
        const { data } = await this.resolvedService.listRemoteBackups(
          destination,
          this.workspace.id
        )
        if (request !== this.loadRequest) {
          return
        }
        this.backups = data.results || []
      } catch (error) {
        if (request !== this.loadRequest) {
          return
        }
        this.backups = []
        // Selecting the same destination again must retry.
        this.loadedDestination = null
        this.handleError(error)
      } finally {
        if (request === this.loadRequest) {
          this.loading = false
        }
      }
    },
    restore(backup) {
      const destination = this.destination
      this.$refs.confirmModal.ask({
        title: this.$t('backupsModal.confirmRestoreTitle'),
        message: this.$t('backupsModal.confirmRestoreMessage', {
          date: this.formatDate(backup.created_on),
        }),
        confirmLabel: this.$t('backupsModal.restore'),
        onConfirm: () => this.doRestore(backup, destination),
      })
    },
    async doRestore(backup, destination) {
      // The backup's key only exists on the destination it was listed from.
      if (destination !== this.destination) {
        return
      }
      this.starting = true
      this.restoringKey = backup.key
      this.hideError()
      try {
        const values = { key: backup.key }
        if (this.isStaff && this.trustPublicKey) {
          values.trust_public_key = true
        }
        const { data } = await this.resolvedService.restoreRemoteBackup(
          destination,
          this.workspace.id,
          values
        )
        await this.createAndMonitorJob(data)
        this.rememberJob('remote', { restoringKey: backup.key })
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
      this.forgetJob('remote')
      await restoredApplicationsFinished(this, this.job, this.workspace.id)
    },
    onJobFailed() {
      this.restoringKey = null
      this.forgetJob('remote')
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },
  },
}
</script>
