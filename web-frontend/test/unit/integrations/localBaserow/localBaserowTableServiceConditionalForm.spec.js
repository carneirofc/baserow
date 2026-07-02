import { defineComponent } from 'vue'

import { TestApp } from '@baserow/test/helpers/testApp'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'

const ViewFieldConditionsFormStub = defineComponent({
  name: 'ViewFieldConditionsForm',
  props: {
    filters: { type: Array, required: true },
  },
  setup() {
    return {
      filterType: {
        hasEditableValue: true,
        isDeprecated: () => false,
        getInputComponent: () => 'input',
      },
    }
  },
  template: `
    <div>
      <slot
        name="filterInputComponent"
        :slot-props="{
          filter: filters[0],
          field: { id: filters[0].field },
          filterType,
        }"
      />
    </div>
  `,
})

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  emits: ['input'],
  template: `
    <button
      class="formula-input-stub"
      @click="$emit('input', { formula: &quot;'Alice'&quot;, mode: 'simple' })"
    />
  `,
})

describe('LocalBaserowTableServiceConditionalForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function mountComponent(modelValue) {
    return await testApp.mount(LocalBaserowTableServiceConditionalForm, {
      props: {
        modelValue,
        fields: [{ id: 1, name: 'Name', primary: true, type: 'text' }],
        filterType: 'AND',
      },
      global: {
        stubs: {
          ViewFieldConditionsForm: ViewFieldConditionsFormStub,
          InjectedFormulaInput: InjectedFormulaInputStub,
        },
      },
    })
  }

  test('emits filters using formula mode instead of value_is_formula', async () => {
    const wrapper = await mountComponent([
      {
        id: 'filter-1',
        field: 1,
        type: 'equal',
        value: { formula: 'Alice', mode: 'raw' },
        value_is_formula: false,
      },
    ])

    await wrapper.find('.formula-input-stub').trigger('click')

    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual([
      {
        id: 'filter-1',
        field: 1,
        type: 'equal',
        value: { formula: "'Alice'", mode: 'simple' },
      },
    ])
  })
})
