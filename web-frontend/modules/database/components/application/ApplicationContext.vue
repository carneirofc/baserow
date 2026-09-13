<template>
  <ApplicationContext
    ref="context"
    :application="application"
    :workspace="workspace"
  >
    <template #additional-context-items>
      <li class="context__menu-item">
        <nuxt-link
          :to="{
            name: 'database-api-docs-detail',
            params: {
              databaseId: application.id,
            },
          }"
          class="context__menu-item-link"
        >
          <i class="context__menu-item-icon iconoir-book"></i>
          {{ $t('sidebar.viewAPI') }}
        </nuxt-link>
      </li>
      <li
        v-if="
          $hasPermission(
            'workspace.list_table_export_schedules',
            workspace,
            workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="openDataExport">
          <i class="context__menu-item-icon iconoir-cloud-upload"></i>
          {{ $t('sidebar.datalakeExports') }}
        </a>
        <DataExportModal
          ref="dataExportModal"
          :database="application"
          :workspace="workspace"
        ></DataExportModal>
      </li>
    </template>
  </ApplicationContext>
</template>

<script>
import ApplicationContext from '@baserow/modules/core/components/application/ApplicationContext.vue'
import applicationContext from '@baserow/modules/core/mixins/applicationContext'
import DataExportModal from '@baserow/modules/database/components/dataExport/DataExportModal'

export default {
  components: {
    ApplicationContext,
    DataExportModal,
  },
  mixins: [applicationContext],
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  methods: {
    openDataExport() {
      this.hide()
      this.$refs.dataExportModal.show()
    },
  },
}
</script>
