<template>
  <div class="backups-admin">
    <h1>{{ $t('adminType.backups') }}</h1>
    <FormGroup :label="$t('backupsAdminPanel.workspace')" small-label>
      <PaginatedDropdown
        :model-value="workspaceId"
        :fetch-page="fetchWorkspaces"
        id-name="id"
        value-name="value"
        size="large"
        :include-display-name-in-selected-event="true"
        @input="workspaceSelected"
      ></PaginatedDropdown>
    </FormGroup>

    <div v-if="loading" class="loading margin-top-2"></div>
    <Tabs
      v-else-if="workspace"
      header-no-padding
      content-no-x-padding
      class="margin-top-2"
    >
      <Tab :title="$t('backupsModal.tabBackups')">
        <BackupsTab
          :workspace="workspace"
          :destinations="destinations"
          :service="adminBackupService"
        />
      </Tab>
      <Tab :title="$t('backupsModal.tabSchedules')">
        <BackupSchedulesTab
          :workspace="workspace"
          :destinations="destinations"
          :service="adminBackupService"
        />
      </Tab>
      <Tab :title="$t('backupsModal.tabRemote')">
        <RemoteBackupsTab
          :workspace="workspace"
          :destinations="destinations"
          :service="adminBackupService"
        />
      </Tab>
    </Tabs>
  </div>
</template>

<script>
import BackupsAdminService from '@baserow/modules/core/services/admin/backups'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import BackupsTab from '@baserow/modules/core/components/backups/BackupsTab'
import BackupSchedulesTab from '@baserow/modules/core/components/backups/BackupSchedulesTab'
import RemoteBackupsTab from '@baserow/modules/core/components/backups/RemoteBackupsTab'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'BackupsAdminPanel',
  components: {
    PaginatedDropdown,
    BackupsTab,
    BackupSchedulesTab,
    RemoteBackupsTab,
  },
  data() {
    return {
      workspaceId: null,
      workspaceName: null,
      loading: false,
      destinations: [],
    }
  },
  computed: {
    workspace() {
      return this.workspaceId
        ? { id: this.workspaceId, name: this.workspaceName }
        : null
    },
  },
  methods: {
    // `service` is passed as a factory function (matching the `(client) => {...}`
    // shape `BackupsTab`/`BackupSchedulesTab`/`RemoteBackupsTab` expect), so the
    // same tab components work here and in the member-facing `BackupsModal`.
    adminBackupService(client) {
      return BackupsAdminService(client)
    },
    fetchWorkspaces(page, search) {
      return BackupsAdminService(this.$client).listWorkspaces(page, search)
    },
    async workspaceSelected({ value, displayName }) {
      this.workspaceId = value
      this.workspaceName = displayName
      await this.loadDestinations()
    },
    async loadDestinations() {
      this.loading = true
      try {
        const { data } = await BackupsAdminService(
          this.$client
        ).listDestinations()
        this.destinations = data.filter((destination) =>
          destination.purposes.includes('backup')
        )
      } catch (error) {
        notifyIf(error)
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
