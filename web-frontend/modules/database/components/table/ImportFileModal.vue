<template>
  <Modal
    ref="modal"
    :right-sidebar="true"
    :right-sidebar-scrollable="true"
    :close-button="false"
    :can-close="!uploadingBeforeJobCreated"
    @show="onShow"
  >
    <template #content>
      <div class="import-modal__header">
        <h2 class="import-modal__title">
          {{
            $t('importFileModal.additionalImportTitle', {
              table: table.name,
            })
          }}
        </h2>
        <div class="modal__actions"></div>
      </div>

      <div v-if="table" class="control margin-bottom-2">
        <FormGroup
          :label="$t('importFileModal.modeLabel')"
          :helper-text="$t('importFileModal.modeDescription')"
          small-label
          required
        >
          <ul class="choice-items margin-top-1">
            <li v-for="option in modeOptions" :key="option.value">
              <a
                class="choice-items__link"
                :class="{
                  active: mode === option.value,
                  disabled:
                    importInProgress || restoredFromStore || !option.allowed,
                }"
                @click="onModeClick(option)"
              >
                <i class="choice-items__icon" :class="option.iconClass"></i>
                <span>{{ option.name }}</span>
                <HelpIcon
                  v-if="!option.allowed"
                  :icon="'lock'"
                  :tooltip="$t('importFileModal.modeNotAllowed')"
                />
                <i
                  v-else-if="mode === option.value"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
          </ul>
        </FormGroup>
      </div>

      <Alert v-if="isReplace" type="error" class="margin-bottom-2">
        <template #title>{{
          $t('importFileModal.replaceWarningTitle')
        }}</template>
        <p>
          {{
            $t('importFileModal.replaceWarningDescription', {
              table: table.name,
            })
          }}
        </p>
        <Checkbox v-model="replaceConfirmed" :disabled="importInProgress">
          {{ $t('importFileModal.replaceConfirm') }}
        </Checkbox>
      </Alert>

      <div class="control margin-bottom-2">
        <FormGroup
          :label="$t('importFileModal.importLabel')"
          small-label
          required
        >
          <ul class="choice-items margin-top-1">
            <li v-for="importerType in importerTypes" :key="importerType.type">
              <a
                class="choice-items__link"
                :class="{
                  active: importer === importerType.type,
                  disabled: importInProgress || restoredFromStore,
                }"
                @click="onImporterClick(importerType.type)"
              >
                <i
                  class="choice-items__icon"
                  :class="importerType.iconClass"
                ></i>
                <span> {{ importerType.getName() }}</span>
                <i
                  v-if="importer === importerType.type"
                  class="choice-items__icon-active iconoir-check-circle"
                ></i>
              </a>
            </li>
          </ul>
        </FormGroup>
      </div>

      <div
        v-if="restoredFromStore && job?.original_file_name"
        class="margin-bottom-2"
      >
        <p>
          {{
            $t('importFileModal.restoredFile', { name: job.original_file_name })
          }}
        </p>
      </div>

      <div v-if="!restoredFromStore" class="margin-bottom-2">
        <component
          :is="importerComponent"
          ref="importerRef"
          :disabled="importInProgress"
          @changed="reset()"
          @header="onHeader($event)"
          @data="onData($event)"
          @get-data="onGetData($event)"
        >
          <template #upsertMapping>
            <div v-if="isUpsert" class="control margin-top-1">
              <label class="control__label control__label--small">
                {{ $t('importFileModal.upsertFieldLabel') }}
                <HelpIcon
                  :icon="'info-empty'"
                  :tooltip="$t('importFileModal.upsertTooltip')"
                />
              </label>

              <Dropdown
                v-model="upsertField"
                :disabled="availableUpsertFields.length === 0"
                class="margin-top-1"
              >
                <DropdownItem
                  v-for="item in availableUpsertFields"
                  :key="item.id"
                  :name="item.name"
                  :value="item.id"
                />
              </Dropdown>
            </div>
          </template>
        </component>
      </div>

      <Alert
        v-if="strictMappingProblems.length > 0"
        type="warning"
        class="margin-bottom-2"
      >
        <template #title>{{
          $t('importFileModal.strictMappingTitle')
        }}</template>
        <ul>
          <li v-for="problem in strictMappingProblems" :key="problem">
            {{ problem }}
          </li>
        </ul>
      </Alert>

      <ImportErrorReport :job="job" :error="error"></ImportErrorReport>

      <Tabs v-if="dataLoaded" header-no-padding content-no-x-padding>
        <Tab :title="$t('importFileModal.importPreview')">
          <SimpleGrid
            class="import-modal__preview"
            :rows="previewImportData"
            :fields="sortedFields"
            :field-options="importFieldOptions"
          />
        </Tab>
        <Tab :title="$t('importFileModal.filePreview')">
          <SimpleGrid
            class="import-modal__preview"
            :rows="previewFileData"
            :fields="fileFields"
            :field-options="fileFieldOptions"
          />
        </Tab>
      </Tabs>

      <div v-if="!hasErrors" class="modal-progress__actions">
        <ProgressBar
          v-if="importInProgress && showProgressBar"
          :value="progressPercentage"
          :status="humanReadableState"
        />
        <ButtonText
          v-if="jobIsRunning || cancelLoading"
          tag="a"
          type="secondary"
          class="modal-progress__cancel-button"
          :loading="cancelLoading"
          @click="cancelJob"
        >
          {{ $t('action.cancel') }}
        </ButtonText>
        <Button
          type="primary"
          size="large"
          full-width
          class="modal-progress__primary-button"
          :loading="importInProgress || (jobIsFinished && !isTableCreated)"
          :disabled="
            importInProgress ||
            !canBeSubmitted ||
            (jobIsFinished && !isTableCreated)
          "
          @click="submitted"
        >
          {{ $t('importFileModal.importButton') }}
        </Button>
      </div>
      <div v-else class="align-right">
        <Button
          type="primary"
          size="large"
          :loading="!isTableCreated"
          @click="openTable()"
        >
          {{ $t('importFileModal.showTable') }}
        </Button>
      </div>
    </template>
    <template #sidebar>
      <div class="import-modal__field-mapping">
        <div v-if="header.length > 0" class="import-modal__field-mapping-body">
          <h3>{{ $t('importFileModal.fieldMappingTitle') }}</h3>
          <p>
            {{ $t('importFileModal.fieldMappingDescription') }}
          </p>
          <FormGroup
            v-for="(head, index) in header"
            :key="head"
            :label="head"
            small-label
            required
            class="margin-bottom-2"
          >
            <Dropdown v-model="mapping[index]">
              <DropdownItem
                v-if="!isStrictMode"
                name="Skip"
                :value="0"
                icon="ban"
              />
              <DropdownItem
                v-for="field in availableFields"
                :key="field.id"
                :name="field.name"
                :value="field.id"
                :icon="field._.type.iconClass"
                :disabled="
                  selectedFields.includes(field.id) &&
                  field.id !== mapping[index]
                "
              />
            </Dropdown>
          </FormGroup>
        </div>
        <div v-else class="import-modal__field-mapping--empty">
          <i class="import-modal__field-mapping-empty-icon iconoir-shuffle" />
          <div class="import-modal__field-mapping-empty-text">
            {{ $t('importFileModal.selectImportMessage') }}
          </div>
        </div>
      </div>
      <div v-if="!uploadingBeforeJobCreated" class="modal__actions">
        <a class="modal__close" @click="hide()">
          <i class="iconoir-cancel"></i>
        </a>
      </div>
    </template>
  </Modal>
</template>

<script>
import { clone } from '@baserow/modules/core/utils/object'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import job from '@baserow/modules/core/mixins/job'
import TableService from '@baserow/modules/database/services/table'
import {
  uuid,
  getNextAvailableNameInSequence,
} from '@baserow/modules/core/utils/string'
import SimpleGrid from '@baserow/modules/database/components/view/grid/SimpleGrid'
import _ from 'lodash'

import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ImportErrorReport from '@baserow/modules/database/components/table/ImportErrorReport.vue'
import { FileImportJobType } from '@baserow/modules/database/jobTypes'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import {
  IMPORT_MODE_APPEND,
  IMPORT_MODE_REPLACE,
  IMPORT_MODE_UPSERT,
  STRICT_IMPORT_MODES,
} from '@baserow/modules/database/constants'
import { nextTick, useNuxtApp } from '#imports'

export default {
  name: 'ImportFileModal',
  components: { ImportErrorReport, SimpleGrid },
  mixins: [modal, error, job],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: false,
      default: null,
    },
    fields: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: ['table-refresh'],
  setup() {
    const nuxtApp = useNuxtApp()
    return { nuxtApp }
  },
  data() {
    return {
      importer: '',
      restoredFromStore: false,
      uploadProgressPercentage: 0,
      importState: null,
      showProgressBar: false,
      header: [],
      mapping: {},
      getData: null,
      previewData: [],
      dataLoaded: false,
      mode: IMPORT_MODE_APPEND,
      replaceConfirmed: false,
      upsertField: undefined,
    }
  },
  computed: {
    sortedFields() {
      // The sort needs to follow the same sort logic as
      // RowHandler.import_rows(...) in the backend
      return [...this.fields].sort((a, b) => {
        const aPrimary = !!a.primary
        const bPrimary = !!b.primary
        if (aPrimary !== bPrimary) return aPrimary ? -1 : 1
        const orderDiff = (a.order ?? 0) - (b.order ?? 0)
        if (orderDiff !== 0) return orderDiff
        return a.id - b.id
      })
    },
    isTableCreated() {
      if (!this.job?.table_id) {
        return false
      }
      return this.database.tables.some(({ id }) => id === this.job.table_id)
    },
    mappingNotEmpty() {
      return Object.values(this.mapping).some(
        (value) => this.fieldIndexMap[value] !== undefined
      )
    },
    isUpsert() {
      return this.mode === IMPORT_MODE_UPSERT
    },
    isReplace() {
      return this.mode === IMPORT_MODE_REPLACE
    },
    isStrictMode() {
      return STRICT_IMPORT_MODES.includes(this.mode)
    },
    modeOptions() {
      const workspaceId = this.database.workspace.id
      return [
        {
          value: IMPORT_MODE_APPEND,
          name: this.$t('importFileModal.modeAppend'),
          iconClass: 'iconoir-plus',
          allowed: this.$hasPermission(
            'database.table.import_rows',
            this.table,
            workspaceId
          ),
        },
        {
          value: IMPORT_MODE_UPSERT,
          name: this.$t('importFileModal.modeUpsert'),
          iconClass: 'iconoir-refresh-double',
          allowed: this.$hasPermission(
            'database.table.upsert_rows',
            this.table,
            workspaceId
          ),
        },
        {
          value: IMPORT_MODE_REPLACE,
          name: this.$t('importFileModal.modeReplace'),
          iconClass: 'iconoir-repeat',
          allowed: this.$hasPermission(
            'database.table.replace_rows',
            this.table,
            workspaceId
          ),
        },
      ]
    },
    /**
     * The file columns the user has not assigned a field to. In a strict mode this
     * is what stops the import: a column the table has no home for would be dropped
     * silently otherwise.
     */
    unmappedFileColumns() {
      return this.header.filter((name, index) => !this.mapping[index])
    },
    /**
     * The importable fields no file column maps onto. In a strict mode these would
     * be blanked (replace) or left stale (upsert) without the user noticing.
     */
    uncoveredFields() {
      const mapped = Object.values(this.mapping)
      return this.availableFields.filter((field) => !mapped.includes(field.id))
    },
    strictMappingProblems() {
      if (!this.isStrictMode || !this.dataLoaded) {
        return []
      }
      const problems = []
      if (this.unmappedFileColumns.length > 0) {
        problems.push(
          this.$t('importFileModal.strictUnmappedColumns', {
            columns: this.unmappedFileColumns.join(', '),
          })
        )
      }
      if (this.uncoveredFields.length > 0) {
        problems.push(
          this.$t('importFileModal.strictUncoveredFields', {
            fields: this.uncoveredFields.map((field) => field.name).join(', '),
          })
        )
      }
      return problems
    },
    canBeSubmitted() {
      if (!this.importer || !this.mappingNotEmpty) {
        return false
      }
      if (this.isStrictMode && this.strictMappingProblems.length > 0) {
        return false
      }
      if (this.isReplace && !this.replaceConfirmed) {
        return false
      }
      if (
        this.isUpsert &&
        !Object.values(this.mapping).includes(this.upsertField)
      ) {
        return false
      }
      return true
    },
    fieldTypes() {
      return this.$registry.getAll('field')
    },
    fileFields() {
      return this.header.map((header, index) => ({
        type: 'text',
        name: header,
        id: uuid(),
        order: index,
      }))
    },
    importFieldOptions() {
      return Object.fromEntries(
        this.sortedFields.map((field) => [field.id, { hidden: false }])
      )
    },
    fileFieldOptions() {
      return Object.fromEntries(
        this.fileFields.map((field) => [field.id, { hidden: false }])
      )
    },
    /**
     * All writable fields.
     */
    writableFields() {
      return this.sortedFields.filter((field) =>
        this.fieldTypes[field.type].canWriteFieldValues(field)
      )
    },
    /**
     * Map beetween the field id and its index in the array.
     */
    fieldIndexMap() {
      return Object.fromEntries(
        this.writableFields.map((field, index) => [field.id, index])
      )
    },
    /**
     * All writable fields that can be imported into
     */
    availableFields() {
      return this.writableFields.filter(({ type }) =>
        this.fieldTypes[type].getCanImport()
      )
    },
    fieldMapping() {
      return Object.entries(this.mapping)
        .filter(
          ([, targetFieldId]) =>
            !!targetFieldId ||
            // Check if we have an id from a removed field
            this.fieldIndexMap[targetFieldId] !== undefined
        )
        .map(([importIndex, targetFieldId]) => {
          return [importIndex, this.fieldIndexMap[targetFieldId]]
        })
    },
    previewFileData() {
      return this.previewData.map((row) => {
        const newRow = Object.fromEntries(
          this.fileFields.map((field, index) => [
            `field_${field.id}`,
            `${row[index]}`,
          ])
        )
        newRow.id = uuid()
        return newRow
      })
    },
    previewImportData() {
      return this.previewData.map((row) => {
        const newRow = Object.fromEntries(
          this.fieldMapping.map(([importIndex, fieldIndex]) => {
            const field = this.writableFields[fieldIndex]
            return [
              `field_${field.id}`,
              this.fieldTypes[field.type].prepareValueForPaste(
                field,
                `${row[importIndex]}`,
                row[importIndex]
              ),
            ]
          })
        )
        newRow.id = uuid()
        return newRow
      })
    },

    /**
     * Fields that are mapped to a column
     */
    selectedFields() {
      return Object.values(this.mapping)
    },
    availableUpsertFields() {
      const selected = Object.values(this.mapping)
      return this.sortedFields.filter((field) => {
        return (
          selected.includes(field.id) && this.fieldTypes[field.type].canUpsert()
        )
      })
    },
    progressPercentage() {
      switch (this.state) {
        case null:
          return 0
        case 'preparingData':
          return 1
        case 'uploading':
          // 10% -> 50%
          return (this.uploadProgressPercentage / 100) * 40 + 10
        default:
          // 50% -> 100%
          return 50 + this.job.progress_percentage / 2
      }
    },
    state() {
      if (this.job === null) {
        return this.importState
      } else {
        return this.job.state
      }
    },
    importInProgress() {
      return (
        this.state !== null &&
        !this.jobIsFinished &&
        !this.jobHasFailed &&
        !this.error.visible
      )
    },
    // True only while uploading the file before the backend job exists.
    // Once the job is created the user can close the modal — the running job
    // is in the store and will be restored on reopen.
    uploadingBeforeJobCreated() {
      return this.job === null && this.importInProgress
    },
    importerTypes() {
      return this.$registry.getAll('importer')
    },
    importerComponent() {
      return this.importer === ''
        ? null
        : this.$registry.get('importer', this.importer).getFormComponent()
    },
    humanReadableState() {
      switch (this.state) {
        case null:
          return ''
        case 'preparingData':
          return this.$t('importFileModal.preparing')
        case 'uploading':
          if (this.uploadProgressPercentage === 100) {
            return this.$t('job.statePending')
          } else {
            return this.$t('importFileModal.uploading')
          }
        default:
          return this.jobHumanReadableState
      }
    },
    hasErrors() {
      return this.job && Object.keys(this.job.report.failing_rows).length > 0
    },
  },
  methods: {
    getDefaultName() {
      const excludeNames = this.database.tables.map((table) => table.name)
      const baseName = this.$t('importFileModal.defaultName')
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    reset(full = true) {
      this.job = null
      this.restoredFromStore = false
      this.uploadProgressPercentage = 0
      this.replaceConfirmed = false
      if (full) {
        this.header = []
        this.importState = null
        this.mapping = {}
        this.getData = null
        this.previewData = []
        this.dataLoaded = false
      }
      this.hideError()
    },
    onModeClick(option) {
      if (!option.allowed || this.importInProgress || this.restoredFromStore) {
        return
      }
      this.mode = option.value
      this.replaceConfirmed = false
    },
    onImporterClick(type) {
      // Don't let the user change the importer while a job is in progress
      // or a running job is being restored.
      if (this.importInProgress || this.restoredFromStore) {
        return
      }
      this.importer = type
      this.reset()
    },
    onData({ header, previewData }) {
      this.header = header
      this.previewData = previewData
      this.mapping = Object.fromEntries(
        header.map((name, index) => {
          const foundField = this.availableFields.find(
            ({ name: fieldName }) => fieldName === name
          )
          return [index, foundField ? foundField.id : 0]
        })
      )
      this.dataLoaded = header.length > 0 || previewData.length > 0
    },
    onGetData(getData) {
      this.getData = getData
    },
    onHeader(header) {
      this.header = header
      this.mapping = Object.fromEntries(
        header.map((name, index) => {
          const foundField = this.availableFields.find(
            ({ name: fieldName }) => fieldName === name
          )
          return [index, foundField ? foundField.id : 0]
        })
      )
    },
    /**
     * When the form is submitted we try to extract the initial data and first row
     * header setting from the values. An importer could have added those, but they
     * need to be removed from the values.
     */
    async submitted() {
      this.showProgressBar = false
      this.reset(false)
      let data = null
      const importConfiguration = {}

      if (this.isUpsert && this.upsertField) {
        // at the moment we use only one field, but the key may be composed of several
        // fields.
        importConfiguration.upsert_fields = [this.upsertField]
        importConfiguration.upsert_values = []
      }

      if (this.isStrictMode) {
        // The backend re-checks this mapping against the table before it writes
        // anything, so the file can never reshape the table's data format.
        importConfiguration.file_header = [...this.header]
        importConfiguration.field_mapping = this.header.map(
          (name, index) => this.mapping[index] || 0
        )
      }

      const mappedFieldIds = Object.values(this.mapping).filter(
        (id) => id !== 0
      )
      const skippedFieldIds = this.writableFields
        .filter((field) => !mappedFieldIds.includes(field.id))
        .map((field) => field.id)

      if (skippedFieldIds.length > 0) {
        importConfiguration.skipped_fields = skippedFieldIds
      }

      if (typeof this.getData === 'function') {
        try {
          this.showProgressBar = true
          this.importState = 'preparingData'
          await this.$ensureRender()

          data = await this.getData()
          const upsertFields = importConfiguration.upsert_fields || []
          const upsertValues = importConfiguration.upsert_values || []
          const upsertFieldIndexes = []

          Object.entries(this.mapping).forEach(
            ([importIndex, targetFieldId]) => {
              if (upsertFields.includes(targetFieldId)) {
                upsertFieldIndexes.push(importIndex)
              }
            }
          )

          const fieldMapping = Object.entries(this.mapping)
            .filter(
              ([, targetFieldId]) =>
                !!targetFieldId ||
                // Check if we have an id from a removed field
                this.fieldIndexMap[targetFieldId] !== undefined
            )
            .map(([importIndex, targetFieldId]) => {
              return [importIndex, this.fieldIndexMap[targetFieldId]]
            })

          // Template row with default values
          const defaultRow = this.writableFields.map((field) =>
            this.fieldTypes[field.type].getDefaultValue(field, true)
          )

          // Precompute the prepare value function for each field
          const prepareValueByField = this.writableFields.map(
            (field) => (value) =>
              this.fieldTypes[field.type].prepareValueForUpdate(
                field,
                this.fieldTypes[field.type].prepareValueForPaste(
                  field,
                  `${value}`,
                  value
                )
              )
          )

          // Processes the data by chunk to avoid UI freezes
          const result = []

          for (const chunk of _.chunk(data, 1000)) {
            result.push(
              chunk.map((row) => {
                const newRow = clone(defaultRow)
                const upsertRow = []
                fieldMapping.forEach(([importIndex, targetIndex]) => {
                  newRow[targetIndex] = prepareValueByField[targetIndex](
                    row[importIndex]
                  )
                  if (upsertFieldIndexes.includes(importIndex)) {
                    upsertRow.push(newRow[targetIndex])
                  }
                })

                if (upsertFields.length > 0 && upsertRow.length > 0) {
                  if (upsertFields.length !== upsertRow.length) {
                    throw new Error(
                      "upsert row length doesn't match required fields"
                    )
                  }
                  upsertValues.push(upsertRow)
                }
                return newRow
              })
            )
            await this.$ensureRender()
          }
          data = result.flat()
          if (upsertFields.length > 0) {
            if (upsertValues.length !== data.length) {
              throw new Error('upsert values lenght mismatch')
            }
            importConfiguration.upsert_values = upsertValues
          }
        } catch (error) {
          this.reset()
          this.handleError(error, 'application')
        }
      }

      this.importState = 'uploading'

      const onUploadProgress = ({ loaded, total }) =>
        (this.uploadProgressPercentage = (loaded / total) * 100)

      try {
        if (data && data.length > 0) {
          this.showProgressBar = true
        }

        const { data: job } = await TableService(this.$client).importData(
          this.table.id,
          data,
          {
            onUploadProgress,
          },
          Object.keys(importConfiguration).length > 0
            ? importConfiguration
            : null,
          {
            mode: this.mode,
            importer_type: this.importer,
            original_file_name: this.$refs.importerRef?.values?.filename || '',
          }
        )
        await this.createAndMonitorJob(job)
      } catch (error) {
        this.handleError(error, 'application', {
          ERROR_MAX_JOB_COUNT_EXCEEDED: new ResponseErrorMessage(
            this.$t('job.errorJobAlreadyRunningTitle'),
            this.$t('job.errorJobAlreadyRunningDescription')
          ),
          ERROR_TABLE_IMPORT_SCHEMA_MISMATCH: new ResponseErrorMessage(
            this.$t('importFileModal.strictMappingTitle'),
            this.$t('importFileModal.strictMappingServerDescription')
          ),
        })
      }
    },
    getCustomHumanReadableJobState(jobState) {
      const translations = {
        'row-import-creation': this.$t('importFileModal.stateRowCreation'),
        'row-import-validation': this.$t('importFileModal.statePreValidation'),
        'row-import-deletion': this.$t('importFileModal.stateRowDeletion'),
        'import-create-table': this.$t('importFileModal.stateCreateTable'),
      }
      return translations[jobState]
    },
    async openTable() {
      // Redirect to the newly created table.
      await this.$router.push({
        name: 'database-table',
        params: {
          databaseId: this.database.id,
          tableId: this.job.table_id,
        },
      })
      await pageFinished(this.nuxtApp)
      await nextTick()
      this.hide()
    },
    onJobFinished() {
      this.$bus.$emit('table-refresh', {
        tableId: this.job.table_id,
      })
      if (!this.hasErrors) {
        this.hide()
      }
    },
    onJobFailed() {
      this.showError(
        new ResponseErrorMessage(
          this.$t('importFileModal.importError'),
          this.job.human_readable_error
        )
      )
    },
    onJobCancelled() {
      this.importer = ''
      this.reset()
    },
    onShow() {
      this.importer = ''
      this.mode = IMPORT_MODE_APPEND
      this.upsertField = undefined
      this.reset()
      this.loadRunningJob()
    },
    loadRunningJob() {
      const runningJob = this.$store.getters['job/getUnfinishedJobs'].find(
        (j) =>
          j.type === FileImportJobType.getType() &&
          j.table_id === this.table?.id
      )
      if (runningJob) {
        this.job = runningJob
        this.restoredFromStore = true
        this.showProgressBar = true
        if (runningJob.mode) {
          this.mode = runningJob.mode
        }
        // Restore the importer type if it's still registered; otherwise the
        // modal shows just the progress bar + file name.
        if (
          runningJob.importer_type &&
          this.$registry.exists('importer', runningJob.importer_type)
        ) {
          this.importer = runningJob.importer_type
        }
      }
    },
  },
}
</script>
