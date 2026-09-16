/**
 * What the runtime branding falls back to when nothing is configured.
 *
 * Lives outside server/branding/ because both sides need it: the Nitro
 * handlers resolve the operator's values against it, and the client plugin
 * falls back to it when the branding config could not be fetched. Keep this
 * module free of node builtins so it can be bundled for the browser.
 */
export const BRANDING_DEFAULTS = {
  siteUrl: 'https://github.com/carneirofc/baserow',
  docsUrl: 'https://github.com/carneirofc/baserow',
  siteTitle: 'Baserow',
  showAttribution: true,
}
