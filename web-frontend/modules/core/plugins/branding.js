import head from '@baserow/modules/core/head'

/**
 * Applies the runtime branding (see modules/core/server/branding/config.js):
 * the app name in the page title, translation overrides, and the theme
 * stylesheet with the color/font overrides.
 *
 * The branding is fetched once during SSR and handed to the client through the
 * payload, so the browser never requests /_branding/config.json itself.
 */
export default defineNuxtPlugin({
  name: 'branding',
  dependsOn: ['i18n'],
  async setup(nuxtApp) {
    const branding = useState('baserow-branding', () => null)

    if (import.meta.server && branding.value === null) {
      try {
        branding.value = await $fetch('/_branding/config.json')
      } catch (error) {
        console.warn('[branding] Could not load the branding config:', error)
        branding.value = {}
      }
    }

    const { appName, messages, version, hasTheme } = branding.value || {}

    if (messages) {
      for (const [locale, localeMessages] of Object.entries(messages)) {
        nuxtApp.$i18n.mergeLocaleMessage(locale, localeMessages)
      }
    }

    const name = appName || head.title
    const link = []
    if (hasTheme) {
      link.push({
        rel: 'stylesheet',
        href: `/_branding/theme.css?v=${version}`,
        key: 'baserow-branding-theme',
        // Render after the bundled stylesheets so the overrides win.
        tagPriority: 'low',
      })
    }

    useHead({
      title: name,
      titleTemplate: (title) =>
        title && title !== name ? `${title} | ${name}` : name,
      link,
    })
  },
})
