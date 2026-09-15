<template>
  <CrudTable :columns="columns" :service="service" row-id-key="id">
    <template #title>
      {{ $t('auditLogAdminTable.title') }}
    </template>
    <template #header-right-side>
      <a class="button button--ghost" @click="exportCsv">
        {{ $t('auditLogAdminTable.export') }}
      </a>
    </template>
  </CrudTable>
</template>

<script>
import AuditLogService from '@baserow/modules/core/services/admin/auditLog'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'

export default {
  name: 'AuditLogAdminTable',
  components: {
    CrudTable,
  },
  data() {
    this.columns = [
      new CrudTableColumn(
        'created_on',
        () => this.$t('auditLogAdminTable.createdOn'),
        LocalDateField,
        true
      ),
      new CrudTableColumn(
        'user_email',
        () => this.$t('auditLogAdminTable.user'),
        SimpleField,
        true
      ),
      new CrudTableColumn(
        'workspace_id',
        () => this.$t('auditLogAdminTable.workspace'),
        SimpleField
      ),
      new CrudTableColumn(
        'action_type',
        () => this.$t('auditLogAdminTable.actionType'),
        SimpleField,
        true
      ),
      new CrudTableColumn(
        'description',
        () => this.$t('auditLogAdminTable.description'),
        SimpleField
      ),
    ]
    this.service = AuditLogService(this.$client)
    return {}
  },
  methods: {
    async exportCsv() {
      const { data } = await this.service.export()
      const url = window.URL.createObjectURL(new Blob([data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'audit-log.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    },
  },
}
</script>
