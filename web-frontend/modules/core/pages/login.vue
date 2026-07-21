<template>
  <div class="auth__wrapper">
    <Login
      :display-header="true"
      :redirect-on-success="true"
      :invitation="invitation"
      :redirect-by-default="redirectByDefault"
      :sso-error="ssoError"
    />
  </div>
</template>

<script setup>
import Login from '@baserow/modules/core/components/auth/Login'
import WorkspaceService from '@baserow/modules/core/services/workspace'

definePageMeta({
  name: 'login',
  layout: 'login',
  middleware: ['settings'],
})

const { $store: store, $client } = useNuxtApp()

const route = useRoute()
const app = useNuxtApp()
const i18n = useI18n()
const config = useRuntimeConfig()
const router = useRouter()

// Redirect logic
if (store.getters['settings/get'].show_admin_signup_page === true) {
  await navigateTo({ name: 'signup' })
} else if (store.getters['auth/isAuthenticated']) {
  await navigateTo({ name: 'dashboard' })
}

// Data fetching - use token in key to avoid caching issues
const invitationToken = route.query.workspaceInvitationToken
const { data } = await useAsyncData(
  `loginData-${invitationToken || 'none'}`,
  async () => {
    // Fetch login options (will populate Vuex store)
    await store.dispatch('authProvider/fetchLoginOptions')
    // Logic from workspaceInvitationToken mixin
    let invitation = null
    if (invitationToken) {
      try {
        const { data } = await WorkspaceService(
          app.$client
        ).fetchInvitationByToken(invitationToken)
        invitation = data
      } catch {}
    }
    return { invitation }
  }
)

// Head
useHead({
  title: i18n.t('login.title'),
  link: [
    {
      rel: 'canonical',
      href:
        config.public.publicWebFrontendUrl +
        router.resolve({ name: 'login' }).href,
    },
  ],
})

const ssoError = computed(() => route.query.error || null)

const redirectByDefault = computed(() => {
  // Never auto-redirect back into a provider that just failed, otherwise the user
  // would be bounced straight back into the failing flow.
  return !(route.query.noredirect === null) && !ssoError.value
})

const invitation = computed(() => data.value?.invitation || null)
</script>
