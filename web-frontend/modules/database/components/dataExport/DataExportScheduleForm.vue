<template>
  <form @submit.prevent="submit">
    <div class="row">
      <div class="col col-6">
        <FormGroup
          small-label
          required
          :label="$t('dataExportModal.name')"
          :error="showErrors && !values.name.trim()"
          class="margin-bottom-2"
        >
          <FormInput
            v-model="values.name"
            :error="showErrors && !values.name.trim()"
          />
          <template #error>{{ $t('error.requiredField') }}</template>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          required
          :label="$t('dataExportModal.destination')"
          class="margin-bottom-2"
        >
          <Dropdown v-model="values.destination">
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
          required
          :label="$t('dataExportModal.cron')"
          :helper-text="$t('dataExportModal.cronHelp')"
          :error="showErrors && !values.cron.trim()"
          class="margin-bottom-2"
        >
          <FormInput
            v-model="values.cron"
            placeholder="0 * * * *"
            :error="showErrors && !values.cron.trim()"
          />
          <template #error>{{ $t('error.requiredField') }}</template>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('dataExportModal.timezone')"
          class="margin-bottom-2"
        >
          <FormInput v-model="values.timezone" placeholder="UTC" />
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('dataExportModal.fullEveryN')"
          :helper-text="$t('dataExportModal.fullEveryNHelp')"
          class="margin-bottom-2"
        >
          <FormInput v-model="values.full_every_n" type="number" />
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('dataExportModal.columnNaming')"
          :helper-text="$t('dataExportModal.columnNamingHelp')"
          class="margin-bottom-2"
        >
          <Dropdown v-model="values.column_naming">
            <DropdownItem
              :name="$t('dataExportModal.columnNamingFieldId')"
              value="field_id"
            ></DropdownItem>
            <DropdownItem
              :name="$t('dataExportModal.columnNamingFieldName')"
              value="field_name"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
      <div class="col col-12">
        <FormGroup
          small-label
          :label="$t('dataExportModal.tables')"
          :error="showErrors && !allTables && selectedTableIds.length === 0"
          class="margin-bottom-2"
        >
          <Checkbox v-model="allTables">
            {{ $t('dataExportModal.allTables') }}
          </Checkbox>
          <template v-if="!allTables">
            <Checkbox
              v-for="table in database.tables || []"
              :key="table.id"
              v-model="tableSelection[table.id]"
            >
              {{ table.name }}
            </Checkbox>
          </template>
          <template #error>{{ $t('dataExportModal.selectTables') }}</template>
        </FormGroup>
      </div>
      <div class="col col-12 margin-bottom-2">
        <Checkbox v-model="values.is_active">
          {{ $t('dataExportModal.active') }}
        </Checkbox>
      </div>
    </div>
    <div class="flex justify-content-end">
      <Button
        type="secondary"
        class="margin-right-1"
        @click.prevent="$emit('cancel')"
      >
        {{ $t('dataExportModal.cancel') }}
      </Button>
      <Button :loading="loading" :disabled="loading" @click.prevent="submit">
        {{ $t('dataExportModal.save') }}
      </Button>
    </div>
  </form>
</template>

<script>
export default {
  name: 'DataExportScheduleForm',
  props: {
    schedule: {
      type: Object,
      required: false,
      default: null,
    },
    database: {
      type: Object,
      required: true,
    },
    destinations: {
      type: Array,
      required: true,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['submit', 'cancel'],
  data() {
    const schedule = this.schedule || {}
    const tableIds = schedule.table_ids ?? null
    const tableSelection = {}
    for (const table of this.database.tables || []) {
      tableSelection[table.id] =
        tableIds !== null && tableIds.includes(table.id)
    }
    return {
      showErrors: false,
      allTables: tableIds === null,
      tableSelection,
      values: {
        name: schedule.name || '',
        cron: schedule.cron || '0 * * * *',
        timezone: schedule.timezone || 'UTC',
        destination: schedule.destination || this.destinations[0]?.name || '',
        full_every_n: schedule.full_every_n ?? 24,
        column_naming: schedule.column_naming || 'field_id',
        is_active: schedule.is_active ?? true,
      },
    }
  },
  computed: {
    selectedTableIds() {
      return Object.entries(this.tableSelection)
        .filter(([, selected]) => selected)
        .map(([id]) => parseInt(id, 10))
    },
  },
  methods: {
    submit() {
      this.showErrors = true
      if (
        !this.values.name.trim() ||
        !this.values.cron.trim() ||
        (!this.allTables && this.selectedTableIds.length === 0)
      ) {
        return
      }
      const fullEveryN = parseInt(this.values.full_every_n, 10)
      this.$emit('submit', {
        ...this.values,
        name: this.values.name.trim(),
        cron: this.values.cron.trim(),
        timezone: this.values.timezone.trim() || 'UTC',
        full_every_n:
          Number.isNaN(fullEveryN) || fullEveryN < 0 ? 24 : fullEveryN,
        table_ids: this.allTables ? null : this.selectedTableIds,
      })
    },
  },
}
</script>
