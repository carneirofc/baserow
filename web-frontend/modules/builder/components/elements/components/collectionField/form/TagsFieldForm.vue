<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('tagsFieldForm.fieldValuesLabel')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput
        v-model="values.values"
        :placeholder="$t('tagsFieldForm.fieldValuesPlaceholder')"
      />
      <template #after-input>
        <CustomStyleButton
          v-model="values.styles"
          style-key="cell"
          :config-block-types="['table', 'typography']"
          :theme="baseTheme"
          :on-styles-changed="onFieldStylesChanged"
          :extra-args="{ onlyCell: true, onlyBody: true, noAlignment: true }"
          variant="normal"
        />
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('tagsFieldForm.fieldColorsLabel')"
      horizontal
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.colors"
        :placeholder="$t('tagsFieldForm.fieldColorsPlaceholder')"
        allow-raw-values
      >
        <template #raw-input="{ value, input }">
          <ColorInput
            :model-value="value"
            :color-variables="colorVariables"
            small
            @update:model-value="input"
          />
        </template>
      </InjectedFormulaInput>
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'

export default {
  name: 'TagsField',
  components: { InjectedFormulaInput, CustomStyleButton },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['values', 'colors', 'styles'],
      values: {
        values: {},
        colors: {
          formula: '#acc8f8',
          mode: 'raw',
        },
        styles: {},
      },
    }
  },
}
</script>
