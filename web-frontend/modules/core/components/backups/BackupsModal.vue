<template>
  <Modal ref="modal" :full-screen="false" :close-button="true">
    <h2 class="box__title">
      {{ $t('backupsModal.title') }} {{ workspace.name }}
    </h2>
    <p>{{ $t('backupsModal.description') }}</p>
    <Error :error="error"></Error>
    <div v-if="loading" class="loading margin-top-2 margin-bottom-2"></div>
    <Tabs v-else-if="loaded" header-no-padding content-no-x-padding>
      <Tab :title="$t('backupsModal.tabBackups')">
        <BackupsTab :workspace="workspace" :destinations="destinations" />
      </Tab>
      <Tab :title="$t('backupsModal.tabSchedules')">
        <BackupSchedulesTab
          :workspace="workspace"
          :destinations="destinations"
        />
      </Tab>
      <Tab :title="$t('backupsModal.tabRemote')">
        <RemoteBackupsTab :workspace="workspace" :destinations="destinations" />
      </Tab>
    </Tabs>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import BackupService from '@baserow/modules/core/services/backup'
import BackupsTab from '@baserow/modules/core/components/backups/BackupsTab'
import BackupSchedulesTab from '@baserow/modules/core/components/backups/BackupSchedulesTab'
import RemoteBackupsTab from '@baserow/modules/core/components/backups/RemoteBackupsTab'

export default {
  name: 'BackupsModal',
  components: { BackupsTab, BackupSchedulesTab, RemoteBackupsTab },
  mixins: [modal, error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      loaded: false,
      destinations: [],
    }
  },
  methods: {
    show(...args) {
      modal.methods.show.bind(this)(...args)
      this.load()
    },
    async load() {
      // The tabs are re-mounted on every open, so they always show fresh data.
      this.loaded = false
      this.loading = true
      this.hideError()
      try {
        const { data } = await BackupService(this.$client).listDestinations()
        this.destinations = data.filter((destination) =>
          destination.purposes.includes('backup')
        )
        this.loaded = true
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
