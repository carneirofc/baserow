<template>
  <div v-if="modelValue">
    <div v-if="modelValue.length === 0">
      <div class="filters__none">
        <div class="filters__none-title">
          {{ $t('localBaserowTableServiceConditionalForm.noFilterTitle') }}
        </div>
        <div class="filters__none-description">
          {{ $t('localBaserowTableServiceConditionalForm.noFilterText') }}
        </div>
      </div>
    </div>
    <ViewFieldConditionsForm
      :filters="getSortedDataSourceFilters()"
      :disable-filter="false"
      :filter-type="filterType"
      :fields="fields"
      :read-only="false"
      class="filters__items"
      :prepare-value="prepareValue"
      :placeholder="
        $t('localBaserowTableServiceConditionalForm.textFilterInputPlaceholder')
      "
      @delete-filter="deleteFilter($event)"
      @update-filter="updateFilter($event)"
      @update-filter-type="$emit('update:filterType', $event.value)"
    >
      <template
        #filterInputComponent="{
          slotProps: { filter, field, filterType: propFilterType },
        }"
      >
        <InjectedFormulaInput
          v-if="
            propFilterType.hasEditableValue && !propFilterType.isDeprecated()
          "
          :model-value="getFormulaObject(filter)"
          class="filters__value--formula-input"
          allow-raw-values
          :placeholder="
            $t(
              'localBaserowTableServiceConditionalForm.formulaFilterInputPlaceholder'
            )
          "
          @input="
            updateFilter({
              filter,
              values: { value: $event.formula, mode: $event.mode },
            })
          "
        >
          <template #raw-input="{ value, input }">
            <component
              :is="propFilterType.getInputComponent(field)"
              :filter="{ ...filter, value }"
              :fields="fields"
              :disabled="false"
              :read-only="false"
              :placeholder="
                $t(
                  'localBaserowTableServiceConditionalForm.textFilterInputPlaceholder'
                )
              "
              @input="input"
              @migrate="updateFilter({ filter, values: $event })"
            />
          </template>
        </InjectedFormulaInput>
      </template>
    </ViewFieldConditionsForm>
    <div class="filters_footer">
      <ButtonText
        type="secondary"
        size="small"
        icon="iconoir-plus"
        class="filters__add"
        @click.prevent="addFilter()"
      >
        {{ $t('localBaserowTableServiceConditionalForm.addFilter') }}
      </ButtonText>
    </div>
  </div>
</template>

<script>
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm.vue'
import { hasCompatibleFilterTypes } from '@baserow/modules/database/utils/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ulid } from 'ulid'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'LocalBaserowTableServiceConditionalForm',
  components: {
    InjectedFormulaInput,
    ViewFieldConditionsForm,
  },
  props: {
    modelValue: {
      type: Array,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    filterType: {
      type: String,
      required: true,
    },
  },
  emits: ['update:modelValue', 'update:filterType'],
  computed: {
    filterTypes() {
      return this.$registry.getAll('viewFilter')
    },
    databaseSelected() {
      return this.databases.find(
        (database) => database.id === this.databaseSelectedId
      )
    },
    tables() {
      return this.databaseSelected?.tables || []
    },
  },
  methods: {
    /*
     * Responsible for returning the first compatible field we have in
     * our schema fields. Used by `addFilter` to decide what the newly
     * added filter's field should be.
     */
    getFirstCompatibleField(fields) {
      return fields
        .slice()
        .sort((a, b) => b.primary - a.primary)
        .find((field) => hasCompatibleFilterTypes(field, this.filterTypes))
    },
    /*
     * Responsible for returning all current data source filters, but
     * sorted by their `order`. Without the sorting, `ViewFieldConditionsForm`
     * will add/update them in a haphazard way.
     */
    getSortedDataSourceFilters() {
      // The `value` prop is an array of filters with a formula object value.
      // The `ViewFieldConditionsForm` expects the filter value itself to be a
      // string, so we keep the mode alongside the flattened formula string.
      const dataSourceFilters = this.modelValue.map((filterConf) => {
        const formulaObject = this.normalizeFormulaObject(filterConf)
        return {
          ...filterConf,
          value: formulaObject.formula,
          mode: formulaObject.mode,
        }
      })
      return dataSourceFilters.sort((a, b) => a.order - b.order)
    },
    /*
     * Responsible for asynchronously adding a new data source filter.
     * By default it'll be for the first compatible field, of type equal,
     * and value blank.
     */
    async addFilter() {
      try {
        const field = this.getFirstCompatibleField(this.fields)
        if (field === undefined) {
          await this.$store.dispatch('toast/error', {
            title: this.$t(
              'localBaserowTableServiceConditionalForm.noCompatibleFilterTypesErrorTitle'
            ),
            message: this.$t(
              'localBaserowTableServiceConditionalForm.noCompatibleFilterTypesErrorMessage'
            ),
          })
        } else {
          const newFilters = [...this.modelValue]
          // Setting an `id` of `ulid` is necessary for two reasons:
          // 1) So that we can distinguish between filters locally
          // 2) It has to match what is sorted against `sortNumbersAndUuid1Asc`.
          newFilters.push({
            id: ulid(),
            field: field.id,
            type: 'equal',
            value: { formula: '', mode: 'raw' },
          })
          this.$emit('update:modelValue', newFilters)
        }
      } catch (error) {
        notifyIf(error, 'dataSource')
      }
    },
    /*
     * Responsible for removing the chosen filter from the data source's filters.
     */
    deleteFilter(filter) {
      const newFilters = this.modelValue.filter(({ id }) => {
        return id !== filter.id
      })
      this.$emit('update:modelValue', newFilters)
    },
    /*
     * Responsible for updating the chosen filter in the data source's filters.
     */
    updateFilter({ filter, values }) {
      const newFilters = this.modelValue.map((filterConf) => {
        if (filterConf.id === filter.id) {
          const mode = values.mode || filter.mode || 'raw'
          const filterValues = { ...filterConf }
          delete filterValues.value
          delete filterValues.value_is_formula
          delete filterValues.mode

          const updatedValues = { ...values }
          delete updatedValues.value
          delete updatedValues.value_is_formula
          delete updatedValues.mode

          return {
            ...filterValues,
            ...updatedValues,
            value: {
              formula: values.value,
              mode,
            },
          }
        }
        return filterConf
      })
      this.$emit('update:modelValue', newFilters)
    },
    /*
     * Responsible for bypassing the `ViewFieldConditionsForm` component's
     * `updateFilter` method behaviour if the field is a formula. By default,
     * when a filter is updated, `filterType.prepareValue` is called. This is
     * problematic because when formulas are introduced to filters, we don't
     * want any additional processing to happen when the value is reset. For example,
     * when a filter on a date is added, `LocalizedDateViewFilterType.prepareValue`
     * will always add the timezone and `DATE_FILTER_TIMEZONE_VALUE_SEPARATOR`.
     */
    prepareValue(value, filter, field, filterType) {
      // When a filter is not editable (e.g. empty/not empty), ordinarily the
      // value is reset to a blank string by prepareValue. As we want to skip
      // this function, we have to reset manually here.
      return filterType.hasEditableValue ? value : ''
    },
    /**
     * Baserow formula (i.e. non-database formulas) are objects, and within
     * them is the actual formula string. This method is responsible for
     * returning that formula string so that it can be passed to the
     * `InjectedFormulaInput` component.
     * @param {Object} filter - The filter object.
     * @returns {Object} The formula object with the formula string.
     */
    getFormulaObject(filter) {
      return {
        formula: filter.value,
        mode: filter.mode || 'raw',
      }
    },
    normalizeFormulaObject(filter) {
      if (filter.value && typeof filter.value === 'object') {
        const mode =
          filter.value.mode || (filter.value_is_formula ? 'simple' : 'raw')
        return {
          ...filter.value,
          mode: filter.value_is_formula === false ? 'raw' : mode,
        }
      }

      return {
        formula: filter.value || '',
        mode: filter.value_is_formula ? 'simple' : 'raw',
      }
    },
  },
}
</script>
