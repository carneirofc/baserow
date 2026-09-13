import { createHash } from 'node:crypto'
import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'

/**
 * Runtime branding: lets operators change the app name, colors, fonts, logos,
 * favicons, icons, translations and extra CSS without rebuilding the frontend.
 *
 * Everything is read from `BASEROW_BRANDING_DIR` (a directory mounted into the
 * container) with a few env var overrides. Every part is optional; with nothing
 * configured the built-in defaults are used unchanged.
 *
 *   branding.json   { appName, colors, fontFamily, messages }
 *   theme.css       free-form CSS appended after the generated variables
 *   img/, icons/    override the default logo/favicon images and icon masks
 *   files/          extra assets that theme.css can reference (e.g. fonts)
 *
 * Values that end up in CSS are validated so a branding file can only set
 * colors and fonts, never inject arbitrary CSS through branding.json.
 */

export const DEFAULT_BRANDING_DIR = '/baserow/branding'

// Only the design tokens defined in modules/core/assets/scss/colors.scss.
const TOKEN_NAME = /^(palette|color)-[a-z]+(-[a-z]+)*-\d+$/
const COLOR_VALUE =
  /^(#[0-9a-f]{3,8}|[a-z]+|(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([0-9a-z.,%\s/+-]+\))$/i
const FONT_FAMILY = /^[\w\s,'"-]+$/
const LOCALE = /^[a-z]{2,3}(-[a-z0-9]{2,8})*$/i
const APP_NAME_MAX_LENGTH = 64
// Re-reading the files on every request is wasteful; changes still apply
// within this window, without restarting the server.
const CACHE_TTL_MS = 2000

let cache = null

const brandingDir = (env) =>
  path.resolve(env.BASEROW_BRANDING_DIR || DEFAULT_BRANDING_DIR)

async function readOptionalFile(file) {
  try {
    const [info, contents] = await Promise.all([
      stat(file),
      readFile(file, 'utf8'),
    ])
    return { mtimeMs: info.mtimeMs, contents }
  } catch (error) {
    if (error.code === 'ENOENT' || error.code === 'ENOTDIR') {
      return null
    }
    throw error
  }
}

function parseJson(text, source, warn) {
  try {
    const value = JSON.parse(text)
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return value
    }
    warn(`${source} must contain a JSON object, ignoring it.`)
  } catch (error) {
    warn(`${source} is not valid JSON (${error.message}), ignoring it.`)
  }
  return {}
}

export function sanitizeColors(colors, warn = () => {}) {
  const valid = {}
  if (!colors || typeof colors !== 'object' || Array.isArray(colors)) {
    return valid
  }
  for (const [name, value] of Object.entries(colors)) {
    if (!TOKEN_NAME.test(name)) {
      warn(`Unknown color token "${name}", ignoring it.`)
    } else if (typeof value !== 'string' || !COLOR_VALUE.test(value.trim())) {
      warn(`Invalid color value for "${name}", ignoring it.`)
    } else {
      valid[name] = value.trim()
    }
  }
  return valid
}

function sanitizeFontFamily(fontFamily, warn) {
  if (fontFamily === undefined || fontFamily === null || fontFamily === '') {
    return null
  }
  if (typeof fontFamily === 'string' && FONT_FAMILY.test(fontFamily)) {
    return fontFamily.trim()
  }
  warn('Invalid fontFamily, ignoring it.')
  return null
}

function sanitizeAppName(appName, warn) {
  if (typeof appName !== 'string') {
    return null
  }
  // Drop control characters; the name is rendered as text, never as HTML.
  // eslint-disable-next-line no-control-regex
  const name = appName.replace(/[\u0000-\u001f\u007f]/g, '').trim()
  if (!name) {
    return null
  }
  if (name.length > APP_NAME_MAX_LENGTH) {
    warn(
      `appName is longer than ${APP_NAME_MAX_LENGTH} characters, truncating.`
    )
  }
  return name.slice(0, APP_NAME_MAX_LENGTH)
}

function onlyStrings(value) {
  if (typeof value === 'string') {
    return value
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const result = {}
    for (const [key, child] of Object.entries(value)) {
      const clean = onlyStrings(child)
      if (clean !== undefined) {
        result[key] = clean
      }
    }
    return result
  }
  return undefined
}

function sanitizeMessages(messages, warn) {
  const valid = {}
  if (!messages || typeof messages !== 'object' || Array.isArray(messages)) {
    return valid
  }
  for (const [locale, localeMessages] of Object.entries(messages)) {
    const clean = onlyStrings(localeMessages)
    if (!LOCALE.test(locale) || !clean || typeof clean !== 'object') {
      warn(`Invalid messages for locale "${locale}", ignoring them.`)
    } else {
      valid[locale] = clean
    }
  }
  return valid
}

/**
 * Renders the stylesheet served at `/_branding/theme.css`: the configured
 * tokens as CSS custom properties, followed by the operator's theme.css.
 */
export function renderThemeCss({ colors, fontFamily, css }) {
  const declarations = Object.entries(colors).map(
    ([name, value]) => `  --${name}: ${value};`
  )
  if (fontFamily) {
    declarations.push(`  --baserow-font-family: ${fontFamily};`)
  }
  const parts = []
  if (declarations.length > 0) {
    parts.push(`:root {\n${declarations.join('\n')}\n}`)
  }
  if (css) {
    parts.push(css)
  }
  return parts.join('\n\n') + '\n'
}

async function buildBranding(env, warn) {
  const dir = brandingDir(env)
  const [jsonFile, cssFile] = await Promise.all([
    readOptionalFile(path.join(dir, 'branding.json')),
    readOptionalFile(path.join(dir, 'theme.css')),
  ])

  const file = jsonFile
    ? parseJson(jsonFile.contents, 'branding.json', warn)
    : {}

  let envColors = {}
  if (env.BASEROW_BRANDING_COLORS) {
    envColors = parseJson(
      env.BASEROW_BRANDING_COLORS,
      'BASEROW_BRANDING_COLORS',
      warn
    )
  }

  const branding = {
    dir,
    // An empty env var counts as unset: Compose passes unset variables
    // through as empty strings.
    appName: sanitizeAppName(
      env.BASEROW_BRANDING_APP_NAME || file.appName,
      warn
    ),
    colors: sanitizeColors({ ...file.colors, ...envColors }, warn),
    fontFamily: sanitizeFontFamily(file.fontFamily, warn),
    messages: sanitizeMessages(file.messages, warn),
    css: cssFile ? cssFile.contents : '',
  }
  branding.themeCss = renderThemeCss(branding)
  // Changes whenever anything that affects the rendered page changes, so it
  // doubles as a cache-busting query string and an ETag.
  branding.version = createHash('sha256')
    .update(
      JSON.stringify([branding.appName, branding.messages, branding.themeCss])
    )
    .digest('hex')
    .slice(0, 16)
  branding.hasTheme = branding.themeCss.trim().length > 0
  return branding
}

/**
 * Returns the current branding, re-reading the branding directory at most once
 * every CACHE_TTL_MS.
 */
export async function loadBranding({
  env = process.env,
  now = Date.now(),
  warn = (message) => console.warn(`[branding] ${message}`),
} = {}) {
  if (cache && cache.env === env && now - cache.loadedAt < CACHE_TTL_MS) {
    return cache.branding
  }
  const branding = await buildBranding(env, warn)
  cache = { env, loadedAt: now, branding }
  return branding
}

export function clearBrandingCache() {
  cache = null
}
