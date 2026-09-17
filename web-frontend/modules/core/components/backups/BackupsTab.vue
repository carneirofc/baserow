<template>
  <div>
    <Error :error="error"></Error>
    <div class="row">
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('backupsModal.destination')"
          class="margin-bottom-2"
        >
          <Dropdown v-model="destination" :disabled="busy">
            <DropdownItem
              :name="$t('backupsModal.noDestination')"
              value=""
            ></DropdownItem>
            <DropdownItem
              v-for="item in destinations"
              :key="item.name"
              :name="item.name"
              :value="item.name"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('backupsModal.content')"
          class="margin-bottom-2"
        >
          <Checkbox v-model="onlyStructure" :disabled="busy">
            {{ $t('backupsModal.onlyStructure') }}
          </Checkbox>
        </FormGroup>
      </div>
    </div>
    <FormGroup
      v-if="applications.length > 0"
      small-label
      :label="$t('backupsModal.scope')"
      class="margin-bottom-2"
    >
      <Checkbox v-model="onlySelectedApplications" :disabled="busy">
        {{ $t('backupsModal.onlySelectedApplications') }}
      </Checkbox>
      <ApplicationSelector
        v-if="onlySelectedApplications"
        class="margin-top-1"
        :workspace="workspace"
        :selected-application-ids="selectedApplicationIds"
        :disabled="busy"
        @update="selectedApplicationIds = $event"
      />
    </FormGroup>

    <template v-if="jobIsRunning">
      <ProgressBar
        :value="job.progress_percentage || 0"
        :status="jobHumanReadableState"
      />
      <JobDuration :job="job" class="margin-bottom-2" />
    </template>
    <Button :loading="busy" :disabled="busy" @click="startBackup">
      {{ $t('backupsModal.backupNow') }}
    </Button>

    <div v-if="loading" class="loading margin-top-3"></div>
    <p v-else-if="backups.length === 0" class="margin-top-3">
      {{ $t('backupsModal.noBackups') }}
    </p>
    <div v-else class="export-workspace__list margin-top-3">
      <div
        v-for="backup in backups"
        :key="backup.id"
        class="export-workspace__export"
      >
        <div class="export-workspace__info">
          <div>
            <div class="export-workspace__name">
              {{ formatDate(backup.created_on) }}
            </div>
            <div class="export-workspace__detail">
              {{ backup.exported_file_name }}
              <template v-if="backup.destination">
                ·
                {{
                  $t('backupsModal.uploadedTo', { name: backup.destination })
                }}
              </template>
            </div>
          </div>
        </div>
        <div class="export-workspace__actions">
          <DownloadLink
            :url="backup.url"
            :filename="backup.exported_file_name"
            :loading-class="'button--loading'"
          >
            {{ $t('backupsModal.download') }}
          </DownloadLink>
          <Button
            type="secondary"
            size="small"
            :disabled="busy"
            @click="restore(backup)"
          >
            {{ $t('backupsModal.restore') }}
          </Button>
          <Button
            type="secondary"
            size="small"
            icon="iconoir-bin"
            :disabled="busy"
            :title="$t('backupsModal.delete')"
            @click="remove(backup)"
          ></Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import job from '@baserow/modules/core/mixins/job'
import moment from '@baserow/modules/core/moment'
import BackupService from '@baserow/modules/core/services/backup'
import ApplicationSelector from '@baserow/modules/core/components/export/ApplicationSelector'
import JobDuration from '@baserow/modules/core/components/job/JobDuration'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'BackupsTab',
  components: { ApplicationSelector, JobDuration },
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
      jobKind: null,
      destination: '',
      onlyStructure: false,
      onlySelectedApplications: false,
      selectedApplicationIds: [],
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
    /**
     * `ApplicationSelector` reads the applications out of the store, which only
     * holds those of the workspace the user has open. The staff admin panel targets
     * an arbitrary workspace, so there the list is empty and the picker is hidden
     * rather than showing the wrong applications.
     */
    applications() {
      return this.$store.getters['application/getAllOfWorkspace'](
        this.workspace
      )
    },
  },
  mounted() {
    this.load()
  },
  methods: {
    formatDate(value) {
      return moment(value).format('YYYY-MM-DD HH:mm')
    },
    async load() {
      this.loading = true
      try {
        const { data } = await this.resolvedService.listBackups(
          this.workspace.id
        )
        this.backups = data.results || []
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
    async run(kind, request) {
      this.starting = true
      this.hideError()
      try {
        const { data } = await request()
        this.jobKind = kind
        await this.createAndMonitorJob(data)
      } catch (error) {
        this.handleError(error)
      } finally {
        this.starting = false
      }
    },
    startBackup() {
      const values = { only_structure: this.onlyStructure }
      if (this.destination) {
        values.destination = this.destination
      }
      if (this.onlySelectedApplications && this.selectedApplicationIds.length) {
        values.application_ids = this.selectedApplicationIds
      }
      return this.run('backup', () =>
        this.resolvedService.startBackup(this.workspace.id, values)
      )
    },
    restore(backup) {
      return this.run('restore', () =>
        this.resolvedService.restoreBackup(
          this.workspace.id,
          backup.resource_id
        )
      )
    },
    async remove(backup) {
      this.hideError()
      try {
        await this.resolvedService.deleteBackup(
          this.workspace.id,
          backup.resource_id
        )
        this.backups = this.backups.filter((item) => item.id !== backup.id)
      } catch (error) {
        this.handleError(error)
      }
    },
    async onJobFinished() {
      if (this.jobKind === 'restore') {
        await restoredApplicationsFinished(this, this.job)
      } else {
        this.$store.dispatch('toast/info', {
          title: this.$t('backupsModal.backupFinishedTitle'),
          message: this.$t('backupsModal.backupFinishedMessage'),
        })
        await this.load()
      }
    },
    onJobFailed() {
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.job.human_readable_error
      )
    },
  },
}

/**
 * Adds the applications installed by a finished restore job to the sidebar and tells
 * the user. Shared by the local and remote restore tabs.
 */
export async function restoredApplicationsFinished(component, finishedJob) {
  const installed = finishedJob.installed_applications || []
  try {
    for (const application of installed) {
      await component.$store.dispatch('application/forceCreate', application)
    }
    component.$store.dispatch('toast/info', {
      title: component.$t('backupsModal.restoreFinishedTitle'),
      message: component.$t('backupsModal.restoreFinishedMessage', {
        count: installed.length,
      }),
    })
  } catch (error) {
    notifyIf(error, 'application')
  }
}
</script>
