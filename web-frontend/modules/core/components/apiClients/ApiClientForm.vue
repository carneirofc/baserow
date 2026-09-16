<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('apiClientForm.nameLabel')"
      small-label
      required
      :error="fieldHasErrors('name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="fieldHasErrors('name')"
        @blur="v$.values.name.$touch()"
      ></FormInput>
      <template #error>{{ getFirstErrorMessage('name') }}</template>
    </FormGroup>

    <FormGroup
      :label="$t('apiClientForm.scopesLabel')"
      :helper-text="$t('apiClientForm.scopesHelp')"
      small-label
      required
      :error="fieldHasErrors('scopes')"
      class="margin-bottom-2"
    >
      <div
        v-for="scope in scopes"
        :key="scope"
        class="api-client__scope margin-bottom-1"
      >
        <Checkbox
          :model-value="values.scopes.includes(scope)"
          @update:model-value="toggleScope(scope, $event)"
        >
          {{ $t(`apiClientScopes.${translationKey(scope)}`) }}
        </Checkbox>
        <div class="api-client__scope-description">
          {{ $t(`apiClientScopes.${translationKey(scope)}Description`) }}
        </div>
      </div>
      <template #error>{{ getFirstErrorMessage('scopes') }}</template>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { helpers, required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import {
  API_CLIENT_SCOPES,
  scopeTranslationKey,
} from '@baserow/modules/core/apiClients/scopes'

export default {
  name: 'ApiClientForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      scopes: API_CLIENT_SCOPES,
      values: {
        name: '',
        scopes: [],
      },
    }
  },
  mounted() {
    this.$refs.name.focus()
  },
  methods: {
    translationKey(scope) {
      return scopeTranslationKey(scope)
    },
    toggleScope(scope, selected) {
      const scopes = this.values.scopes.filter((s) => s !== scope)
      if (selected) {
        // Keep the backend's order so the stored list is stable regardless of the
        // order the boxes were ticked in.
        scopes.push(scope)
        scopes.sort((a, b) => this.scopes.indexOf(a) - this.scopes.indexOf(b))
      }
      this.values.scopes = scopes
      this.v$.values.scopes.$touch()
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        scopes: {
          // `minLength` skips values it considers empty, so an empty array would
          // pass it. `required` is the one that rejects a zero length array.
          required: helpers.withMessage(
            this.$t('apiClientForm.scopeRequired'),
            required
          ),
        },
      },
    }
  },
}
</script>
