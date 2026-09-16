/**
 * Mirrors `ALL_SCOPES` in `baserow.core.api_clients.scopes`, in the same order. The
 * backend rejects anything it does not know, so this list must stay in sync with it.
 */
export const API_CLIENT_SCOPES = [
  'backup.read',
  'backup.write',
  'backup.restore',
  'contents.read',
  'schedule.read',
  'schedule.write',
]

/**
 * Turns a scope into the suffix of its translation keys, e.g. `backup.read` into
 * `backupRead`, so `apiClientScopes.backupRead` names it and
 * `apiClientScopes.backupReadDescription` explains it.
 */
export const scopeTranslationKey = (scope) => {
  const [group, action] = scope.split('.')
  return `${group}${action.charAt(0).toUpperCase()}${action.slice(1)}`
}
