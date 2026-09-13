<template>
  <form @submit.prevent="submit">
    <div class="row">
      <div class="col col-6">
        <FormGroup
          small-label
          required
          :label="$t('backupsModal.name')"
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
          :label="$t('backupsModal.destination')"
          class="margin-bottom-2"
        >
          <Dropdown v-model="values.destination">
            <DropdownItem
              :name="$t('backupsModal.noDestination')"
              value=""
            ></DropdownItem>
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
          :label="$t('backupsModal.cron')"
          :helper-text="$t('backupsModal.cronHelp')"
          :error="showErrors && !values.cron.trim()"
          class="margin-bottom-2"
        >
          <FormInput
            v-model="values.cron"
            placeholder="0 3 * * *"
            :error="showErrors && !values.cron.trim()"
          />
          <template #error>{{ $t('error.requiredField') }}</template>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('backupsModal.timezone')"
          class="margin-bottom-2"
        >
          <FormInput v-model="values.timezone" placeholder="UTC" />
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('backupsModal.keepLast')"
          :helper-text="$t('backupsModal.retentionHelp')"
          class="margin-bottom-2"
        >
          <FormInput v-model="values.keep_last" type="number" />
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('backupsModal.keepDays')"
          class="margin-bottom-2"
        >
          <FormInput v-model="values.keep_days" type="number" />
        </FormGroup>
      </div>
      <div class="col col-12 margin-bottom-2">
        <Checkbox v-model="values.only_structure">
          {{ $t('backupsModal.onlyStructure') }}
        </Checkbox>
        <Checkbox v-model="values.is_active">
          {{ $t('backupsModal.active') }}
        </Checkbox>
      </div>
    </div>
    <div class="flex justify-content-end">
      <Button
        type="secondary"
        class="margin-right-1"
        @click.prevent="$emit('cancel')"
      >
        {{ $t('backupsModal.cancel') }}
      </Button>
      <Button :loading="loading" :disabled="loading" @click.prevent="submit">
        {{ $t('backupsModal.save') }}
      </Button>
    </div>
  </form>
</template>

<script>
function toPositiveIntOrNull(value) {
  const number = parseInt(value, 10)
  return Number.isNaN(number) || number < 1 ? null : number
}

export default {
  name: 'BackupScheduleForm',
  props: {
    schedule: {
      type: Object,
      required: false,
      default: null,
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
    return {
      showErrors: false,
      values: {
        name: schedule.name || '',
        cron: schedule.cron || '0 3 * * *',
        timezone: schedule.timezone || 'UTC',
        destination: schedule.destination || '',
        keep_last: schedule.keep_last ?? '',
        keep_days: schedule.keep_days ?? '',
        only_structure: schedule.only_structure || false,
        is_active: schedule.is_active ?? true,
      },
    }
  },
  methods: {
    submit() {
      this.showErrors = true
      if (!this.values.name.trim() || !this.values.cron.trim()) {
        return
      }
      this.$emit('submit', {
        ...this.values,
        name: this.values.name.trim(),
        cron: this.values.cron.trim(),
        timezone: this.values.timezone.trim() || 'UTC',
        keep_last: toPositiveIntOrNull(this.values.keep_last),
        keep_days: toPositiveIntOrNull(this.values.keep_days),
      })
    },
  },
}
</script>
