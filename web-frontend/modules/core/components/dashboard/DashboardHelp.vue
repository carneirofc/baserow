<template>
  <Alert
    v-if="displayAlert"
    type="blank"
    close-button
    class="dashboard__help"
    :width="396"
    @close="handleAlertClose"
  >
    <template #image>
      <img
        src="@baserow/modules/core/assets/images/dashboard_alert_image.png"
        srcset="
          @baserow/modules/core/assets/images/dashboard_alert_image@2x.png 2x
        "
      />
    </template>

    <template #title>
      <h4>{{ $t('dashboard.alertTitle') }}</h4>
    </template>

    <p>{{ $t('dashboard.alertText') }}</p>

    <template #actions>
      <Button
        tag="a"
        :href="branding.siteUrl"
        target="_blank"
        rel="noopener noreferrer"
        type="secondary"
        icon="iconoir-github"
      >
        {{ $t('dashboard.starOnGitHub') }}
      </Button>

      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnTwitter')"
        tag="a"
        tooltip-position="top"
        :href="twitterUrl"
        target="_blank"
        rel="noopener noreferrer"
        icon="baserow-icon-twitter"
      />

      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnReddit')"
        tag="a"
        tooltip-position="top"
        icon="baserow-icon-reddit"
        :href="redditUrl"
        target="_blank"
        rel="noopener noreferrer"
      />

      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnFacebook')"
        tag="a"
        tooltip-position="top"
        icon="baserow-icon-facebook"
        :href="facebookUrl"
        target="_blank"
        rel="noopener noreferrer"
      />

      <ButtonIcon
        v-tooltip="$t('dashboard.shareOnLinkedIn')"
        tag="a"
        tooltip-position="top"
        icon="baserow-icon-linkedin"
        :href="linkedInUrl"
        target="_blank"
        rel="noopener noreferrer"
      />
    </template>
  </Alert>
</template>

<script setup>
import { getCookieName } from '@baserow/modules/core/utils/cookie'

const helpDisplayCookieName = 'baserow_dashboard_alert_closed_v2'
const config = useRuntimeConfig()
// This alert promotes the upstream project, so it follows the same switch as
// the rest of the attribution.
const { $branding: branding } = useNuxtApp()

const showAlert = ref(true)

const closedCookie = useCookie(getCookieName(config, helpDisplayCookieName), {
  maxAge: 60 * 60 * 24 * 182, // 6 months
  path: '/',
})

const displayAlert = computed(
  () => branding.showAttribution && showAlert.value && !closedCookie.value
)

const handleAlertClose = () => {
  showAlert.value = false
  closedCookie.value = true
}

const { t } = useI18n()

const sharedUrl = computed(() => encodeURIComponent(branding.siteUrl))

const twitterUrl = computed(
  () =>
    `https://twitter.com/intent/tweet?url=${
      sharedUrl.value
    }&hashtags=opensource,nocode,database,baserow&text=${encodeURI(
      t('dashboard.tweetContent')
    )}`
)

const redditUrl = computed(
  () =>
    `https://www.reddit.com/submit?url=${sharedUrl.value}&title=${encodeURI(
      t('dashboard.redditTitle')
    )}`
)

const facebookUrl = computed(
  () => `https://www.facebook.com/sharer/sharer.php?u=${sharedUrl.value}`
)

const linkedInUrl = computed(
  () => `https://www.linkedin.com/sharing/share-offsite/?url=${sharedUrl.value}`
)
</script>
