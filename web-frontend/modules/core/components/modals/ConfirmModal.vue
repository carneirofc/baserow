<template>
  <Modal ref="modal" small :close-button="false" @hidden="pending = null">
    <h2 class="box__title">{{ title }}</h2>
    <p>{{ message }}</p>
    <div class="actions">
      <ul class="action__links">
        <li>
          <a @click.prevent="cancel">{{ $t('action.cancel') }}</a>
        </li>
      </ul>
      <Button type="danger" @click.prevent="confirm">
        {{ confirmLabel }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

/**
 * Generic "are you sure" modal for a destructive action. The caller opens it with
 * `ask({ title, message, confirmLabel, onConfirm })`; `onConfirm` only runs when
 * the user confirms, so a single misclick never deletes, restores or resets
 * anything.
 */
export default {
  name: 'ConfirmModal',
  mixins: [modal],
  emits: ['confirm', 'cancel'],
  data() {
    return {
      title: '',
      message: '',
      confirmLabel: '',
      pending: null,
    }
  },
  methods: {
    ask({ title, message, confirmLabel, onConfirm }) {
      this.title = title
      this.message = message
      this.confirmLabel = confirmLabel || this.$t('action.delete')
      this.pending = onConfirm || null
      this.show()
    },
    cancel() {
      this.pending = null
      this.$emit('cancel')
      this.hide()
    },
    confirm() {
      const onConfirm = this.pending
      this.pending = null
      this.$emit('confirm')
      this.hide()
      return onConfirm ? onConfirm() : undefined
    },
  },
}
</script>
