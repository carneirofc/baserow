# Single sign-on with OpenID Connect (OIDC)

Baserow signs users in through any OpenID Connect provider — Keycloak/RHBK, Authentik,
Zitadel, Entra ID, Okta and so on — configured entirely through environment variables.
There is no admin UI and no provider row to manage: the environment is the source of truth.

Access is derived from **roles the IdP puts in the token**. A provider maps those roles
to three things:

* **Global authority** — Baserow staff or superuser, instance-wide.
* **Workspace membership** — which workspaces a user joins, as `ADMIN` or `MEMBER`.
* **Granular workspace roles** — a named set of operations a `MEMBER` is restricted to.

A user holding none of the mapped roles is refused at login, and no account is created.

This page is the full reference. For a click-by-click Keycloak walkthrough with
day-to-day operations and hardening, see
[Single sign-on with RHBK/Keycloak](sso-rhbk-keycloak.md).

## Contents

* [Environment variables](#environment-variables)
* [Registering Baserow with the IdP](#registering-baserow-with-the-idp)
* [Provider reference](#provider-reference)
* [Roles and permissions](#roles-and-permissions)
* [How access is decided on each login](#how-access-is-decided-on-each-login)
* [Complete example](#complete-example)
* [Passing the configuration to Baserow](#passing-the-configuration-to-baserow)
* [Configuring RHBK/Keycloak](#configuring-rhbkkeycloak)
* [Login error codes](#login-error-codes)
* [Security notes](#security-notes)
* [Troubleshooting](#troubleshooting)

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `BASEROW_OIDC_PROVIDERS` | `[]` | JSON list of providers. See [Provider reference](#provider-reference). |
| `BASEROW_ROLES` | `[]` | JSON list of granular workspace roles a mapping may grant. See [Granular roles](#3-granular-workspace-roles-baserow_roles). |
| `BASEROW_OIDC_ONLY` | `false` | OIDC-only mode for normal users: password signup is disabled, password login is refused for non-staff accounts and the login page shows only the SSO buttons. A staff/superuser account can still use the password form through **display password login**, so an IdP outage cannot lock you out. Create that break-glass account **before** turning this on. |
| `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT` | unset | When set, an account created through one method (password, another provider) may also sign in through this provider. Leave unset unless you need it; see [Security notes](#security-notes). |

`BASEROW_OIDC_PROVIDERS` and `BASEROW_ROLES` are parsed and validated **once, at
startup**:

* An invalid value stops the backend from starting with an `ImproperlyConfigured` error
  naming the offending entry and key — it never fails later at login.
* **Every change needs a backend restart** (and the Celery workers, which share the
  settings).
* Checks that need the network or the database — issuer discovery, workspace ids, role
  and operation names — happen at login or reconcile time, and are logged.

## Registering Baserow with the IdP

Whatever the provider, register Baserow as a client with these properties:

| Setting | Value |
| --- | --- |
| Client type | Confidential (Baserow authenticates with a client secret) |
| Flow | Authorization code (standard flow). Implicit, password and client-credentials grants are unused. |
| Redirect / callback URI | `<BASEROW_PUBLIC_URL>/api/sso/oidc/callback/<name>/` — `<name>` is the provider's `name`, and the trailing slash is required. Example: `https://baserow.example.com/api/sso/oidc/callback/rhbk/` |
| PKCE | `S256`. Baserow always sends a PKCE challenge; enforcing it on the IdP is recommended. |
| Scopes | `openid`, `email`, `profile` (the default) |
| ID token signing | RSA (`RS256` and friends) — the key is looked up in the IdP's JWKS by `kid` |

What Baserow needs from the IdP at runtime:

* **Discovery.** Baserow fetches `<issuer>/.well-known/openid-configuration` and uses its
  `issuer`, `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint` and `jwks_uri`.
  The backend itself makes these calls, server to server, so it must reach the IdP over the
  network and trust its TLS certificate.
* **An ID token** whose signature, `iss` (must equal the discovered issuer), `aud` (must
  contain `client_id`), `exp`, `iat`, `sub` and `nonce` all verify.
* **A userinfo response** whose `sub` equals the ID token's `sub`, and which carries the
  email claim.
* **An email address**, and — unless `require_verified_email` is `false` — an
  `email_verified` claim that is exactly `true` (read from userinfo, falling back to the
  ID token).
* **Roles** under `roles_claim`, in the ID token, the userinfo response, or both.

## Provider reference

Each element of `BASEROW_OIDC_PROVIDERS` is an object with these keys.

### Identity and connection

| Key | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | yes | — | Stable slug: letters, digits, `-` and `_` only, unique across providers. Appears in the callback URL and links Baserow accounts to this provider, so do not rename it once users have signed in. |
| `display_name` | no | `name` | Label on the login button. |
| `issuer` | yes | — | The provider's issuer URL (`http` or `https`), without `/.well-known/openid-configuration`. |
| `client_id` | yes | — | Client id registered in the IdP. Also the expected ID token audience. |
| `client_secret` | yes | — | Client secret. |
| `scopes` | no | `["openid", "email", "profile"]` | Requested scopes. Must include `openid`. |

### Claims

| Key | Default | Description |
| --- | --- | --- |
| `email_claim` | `email` | Claim in the userinfo response holding the email address. Accounts are matched by email. |
| `name_claim` | `name` | Claim in the userinfo response holding the display name. Falls back to the email when empty. |
| `roles_claim` | `resource_access.${client_id}.roles` | Claim path holding the user's roles. See below. |

`roles_claim` rules:

* It is a **dotted path** into the claims: `resource_access.baserow.roles` reads
  `{"resource_access": {"baserow": {"roles": [...]}}}`.
* `${client_id}` is replaced with the provider's `client_id`, so Keycloak's default mapper
  claim name can be pasted in verbatim.
* A literal dot inside a claim name is escaped as `\.` (in JSON: `"\\."`). If the dotted
  walk does not resolve, the whole string is also tried as one flat key.
* The value may be a list of strings or a single string. Anything else counts as no roles.
* Roles are read from **both** the ID token and the userinfo response, and unioned.

Common values:

| IdP | `roles_claim` |
| --- | --- |
| Keycloak/RHBK client roles | `resource_access.${client_id}.roles` (default) |
| Keycloak/RHBK realm roles | `realm_access.roles` |
| Keycloak group membership mapper, Authentik, Zitadel/Okta custom claim | `groups` (or whatever the mapper emits) |
| Entra ID app roles | `roles` |

The rest of this page says "client role" for whatever strings `roles_claim` yields.

### Access mapping

| Key | Default | Description |
| --- | --- | --- |
| `superuser_roles` | `[]` | Roles whose holders become Baserow **superuser** (which also implies staff). |
| `staff_roles` | `[]` | Roles whose holders become Baserow **staff**. |
| `workspace_mappings` | `[]` | List of workspace mappings, below. |
| `strict_membership` | `false` | When `true`, workspace memberships this provider created are revoked once the user no longer holds the mapped role. Memberships added by hand are never touched. |

Each `workspace_mappings` entry:

| Key | Required | Description |
| --- | --- | --- |
| `client_role` | yes | The role (as found under `roles_claim`) that triggers this mapping. Matched exactly. |
| `workspace` | yes | **Numeric** workspace id (not the name). |
| `permissions` | yes | `ADMIN` or `MEMBER`. |
| `role` | no | Name of a [`BASEROW_ROLES`](#3-granular-workspace-roles-baserow_roles) entry declared for the **same** workspace, restricting the member to its operations. Cannot be combined with `ADMIN`. Omit for an unrestricted member. |

### Session and verification

| Key | Default | Description |
| --- | --- | --- |
| `require_verified_email` | `true` | Refuse users whose `email_verified` claim is not `true` (`errorEmailNotVerified`). Set `false` only when the IdP's email addresses are authoritative, for example LDAP/AD-federated. |
| `link_existing_accounts` | `false` | When `true`, an existing account created by another method (password, another provider) is linked to this provider on first sign-in instead of being refused with `errorDifferentProvider` — only when the IdP sends `email_verified: true` (even with `require_verified_email: false`), and never for staff or superuser accounts. See [Recovering locked-out accounts](#recovering-locked-out-accounts). |
| `session_lifetime_minutes` | `480` | Lifetime of a session started through this provider. Once it ends the user signs in again, which is when role changes apply. Positive integer, or `null` to use `BASEROW_REFRESH_TOKEN_LIFETIME_HOURS`. |

### Retired keys

Older configurations are refused at startup with a message naming the replacement,
because silently ignoring them would drop the access they used to grant:

| Retired | Replacement |
| --- | --- |
| `groups_claim` | `roles_claim` |
| `staff_groups` | `staff_roles` |
| `superuser_groups` | `superuser_roles` |
| `workspace_mappings[].group` | `workspace_mappings[].client_role` |
| `workspace_mappings[].role: "ADMIN"` / `"MEMBER"` | `workspace_mappings[].permissions` (`role` now names a `BASEROW_ROLES` entry) |

## Roles and permissions

Baserow has three independent layers. A provider can set any combination of them.

### 1. Global roles

| Baserow role | Granted by | What it allows |
| --- | --- | --- |
| Superuser | `superuser_roles` | Everything staff can do, plus superuser-only admin actions. Always also staff. |
| Staff | `staff_roles` | The admin area: instance settings, users, all workspaces, application-type toggles. |
| Regular user | neither | Only the workspaces they are a member of. |

Global roles are **reconciled on every login through this provider**: granted when the
user holds a mapped role, revoked when not. Only the dimension you configure is touched —
a provider with no `staff_roles` never changes anyone's staff flag. A local admin who never
signs in through SSO is never modified.

### 2. Workspace permissions

| `permissions` | What it allows in that workspace |
| --- | --- |
| `ADMIN` | Everything, including inviting and removing members, changing their permissions and deleting the workspace. **Not restricted by granular roles.** |
| `MEMBER` | Work with the workspace's applications. Unrestricted unless the mapping names a `role`. |

`ADMIN` is scoped to one workspace and carries no instance-wide authority; that is what
staff/superuser is for.

### 3. Granular workspace roles (`BASEROW_ROLES`)

A granular role restricts a `MEMBER` to an explicit list of operations; **anything not
listed is denied**. Declare roles in `BASEROW_ROLES`:

| Key | Required | Description |
| --- | --- | --- |
| `workspace` | yes | Numeric workspace id the role belongs to. |
| `name` | yes | Role name, unique per workspace. Referenced by `workspace_mappings[].role`. |
| `operations` | no (default `[]`) | Operation names from the table below. |

Reconciliation:

* Roles are written to the database after every `migrate` and whenever you run the
  `sync_roles` management command. Workspaces are usually created after deploying, so
  **run `sync_roles` once the workspace exists**:

  ```bash
  # all-in-one image
  docker exec baserow ./baserow.sh backend-cmd manage sync_roles
  # Compose stack
  docker compose exec backend /baserow/backend/docker/docker-entrypoint.sh manage sync_roles
  # Helm
  kubectl -n baserow exec deploy/baserow-backend -- \
    /baserow/backend/docker/docker-entrypoint.sh manage sync_roles
  # development checkout
  just backend manage sync_roles
  ```

  Adjust the container, service or deployment name to your installation.
* A role for a workspace id that does not exist is skipped with a warning.
* An operation that is misspelled or not in the table below is skipped with a warning; the
  rest of the role is still applied.
* Re-running replaces the role's operations with the declared list.
* A role removed from `BASEROW_ROLES` is **left in the database**, because members may
  still be assigned to it. Remove the mapping first.

#### All available operations

These are every operation a granular role can grant:

| Component | Create | Read | Update | Delete |
| --- | --- | --- | --- | --- |
| Database tables | `database.create_table` | `database.table.read` | `database.table.update` | `database.table.delete` |
| Database fields | `database.table.create_field` | `database.table.field.read` | `database.table.field.update` | `database.table.field.delete` |
| Database rows | `database.table.create_row` | `database.table.read_row` | `database.table.update_row` | `database.table.delete_row` |
| Database views | `database.table.create_view` | `database.table.view.read` | `database.table.view.update` | `database.table.view.delete` |
| Application builder pages | `builder.create_page` | `builder.page.read` | `builder.page.update` | `builder.page.delete` |
| Application builder elements | `builder.page.create_element` | `builder.page.element.read` | `builder.page.element.update` | `builder.page.element.delete` |
| Automation workflows | `automation.create_workflow` | `automation.workflow.read` | `automation.workflow.update` | `automation.workflow.delete` |
| Automation nodes | `automation.workflow.create_node` | `automation.node.read` | `automation.node.update` | `automation.node.delete` |
| Workspace | — | `workspace.read` | `workspace.update` | `workspace.delete` |

Operations build on each other: reading rows is useless without reading the table, its
fields and a view. Grant the whole read path for every component you expose.

#### Role recipes

Starting points — adjust the workspace id and trim what you do not use.

**Reader** — browse databases, change nothing:

```json
{
  "workspace": 1,
  "name": "Reader",
  "operations": [
    "workspace.read",
    "database.table.read",
    "database.table.field.read",
    "database.table.read_row",
    "database.table.view.read"
  ]
}
```

**Data editor** — create, edit and delete rows, but not change the schema:

```json
{
  "workspace": 1,
  "name": "Data editor",
  "operations": [
    "workspace.read",
    "database.table.read",
    "database.table.field.read",
    "database.table.view.read",
    "database.table.read_row",
    "database.table.create_row",
    "database.table.update_row",
    "database.table.delete_row"
  ]
}
```

**Schema designer** — full database authoring, no workspace settings:

```json
{
  "workspace": 1,
  "name": "Schema designer",
  "operations": [
    "workspace.read",
    "database.create_table",
    "database.table.read",
    "database.table.update",
    "database.table.delete",
    "database.table.create_field",
    "database.table.field.read",
    "database.table.field.update",
    "database.table.field.delete",
    "database.table.create_row",
    "database.table.read_row",
    "database.table.update_row",
    "database.table.delete_row",
    "database.table.create_view",
    "database.table.view.read",
    "database.table.view.update",
    "database.table.view.delete"
  ]
}
```

**App builder** — build pages on existing data:

```json
{
  "workspace": 1,
  "name": "App builder",
  "operations": [
    "workspace.read",
    "database.table.read",
    "database.table.field.read",
    "database.table.read_row",
    "database.table.view.read",
    "builder.create_page",
    "builder.page.read",
    "builder.page.update",
    "builder.page.delete",
    "builder.page.create_element",
    "builder.page.element.read",
    "builder.page.element.update",
    "builder.page.element.delete"
  ]
}
```

**Automation operator** — maintain workflows without touching data design:

```json
{
  "workspace": 1,
  "name": "Automation operator",
  "operations": [
    "workspace.read",
    "database.table.read",
    "database.table.field.read",
    "database.table.read_row",
    "automation.create_workflow",
    "automation.workflow.read",
    "automation.workflow.update",
    "automation.workflow.delete",
    "automation.workflow.create_node",
    "automation.node.read",
    "automation.node.update",
    "automation.node.delete"
  ]
}
```

### Finding workspace ids

Mappings and roles use the numeric workspace id:

* **Admin area → Workspaces** (`/admin/workspaces`, staff only), sortable by id.
* **The URL** of an open workspace: `/workspace/<id>`.
* **The API**: `GET /api/admin/workspaces/` with a staff token.

Ids are per database. A configuration copied from staging to production grants access
to whatever workspaces hold those ids there — re-check them after every copy.

## How access is decided on each login

1. **Verify.** `state`, PKCE verifier, ID token (signature, issuer, audience, expiry,
   nonce) and userinfo `sub` must all check out, otherwise `errorAuthFlowError`. A missing
   email is also `errorAuthFlowError`; an unverified one is `errorEmailNotVerified`.
2. **Collect roles** from `roles_claim` in the ID token and userinfo, unioned.
3. **Deny by default.** If the provider maps any role (`superuser_roles`, `staff_roles`
   or `workspace_mappings`) and the user holds none of them, the login is refused with
   `errorNoMappedRole` — **before** an account is created. A provider that maps no role at
   all is not gated: every IdP user may sign in, with no memberships.
4. **Find or create the account** by email. New accounts are provisioned automatically,
   even when the instance has new signups disabled and even with `BASEROW_OIDC_ONLY`. An
   existing account created by another method is refused with `errorDifferentProvider`,
   unless the provider sets `link_existing_accounts` (verified email, non-staff accounts
   only — the account is then linked) or
   `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT` is set. A deactivated
   account is refused with `errorUserDeactivated`.
5. **Reconcile global roles** (`superuser_roles`, `staff_roles`), grant and revoke.
6. **Reconcile workspace memberships** for every mapping whose `client_role` the user holds:
   * the membership is created, or an existing one is updated, to the mapping's
     `permissions` and `role` — the sync is authoritative for the workspaces it maps, so
     removing `role` from a mapping restores full member access on the next login;
   * if two matching mappings target the same workspace, `ADMIN` wins; between two
     `MEMBER` mappings, the first listed wins (a warning is logged);
   * a workspace id that does not exist is skipped with a warning;
   * a `role` that does not exist in that workspace **fails closed**: the membership is
     not granted, and an error is logged.
7. **Revoke** (only with `strict_membership: true`): memberships this provider created
   earlier, whose role the user no longer holds, are removed. Memberships added by hand
   are never tracked and never revoked, and a workspace's last admin is never removed.
8. **Start a session** bounded by `session_lifetime_minutes`.

Everything is applied at login. Removing a role in the IdP does not end a session that is
already open; it applies when the session expires and the user signs in again. To cut
access immediately, disable the user in the IdP **and** deactivate the account in
Baserow's admin area.

## Complete example

Scenario: two identity providers and three workspaces.

| Workspace | Id |
| --- | --- |
| Engineering | `1` |
| Finance | `2` |
| Customer portal | `3` |

| Provider | Role in token | Grants |
| --- | --- | --- |
| `rhbk` (Keycloak client roles) | `baserow-superusers` | global superuser |
| | `baserow-staff` | global staff |
| | `eng-leads` | Engineering `ADMIN` |
| | `eng` | Engineering `MEMBER`, unrestricted |
| | `eng-readonly` | Engineering `MEMBER`, `Reader` |
| | `finance` | Finance `MEMBER`, `Data editor` |
| | `portal-builders` | Customer portal `MEMBER`, `App builder` |
| `partners` (generic IdP, `groups` claim) | `partner-ops` | Customer portal `MEMBER`, `Automation operator` |
| | `partner-viewers` | Finance `MEMBER`, `Reader` |

`BASEROW_OIDC_PROVIDERS` — every key shown, defaults written out explicitly:

```json
[
  {
    "name": "rhbk",
    "display_name": "Company SSO",
    "issuer": "https://keycloak.example.com/realms/main",
    "client_id": "baserow",
    "client_secret": "change-me-rhbk-secret",
    "scopes": ["openid", "email", "profile"],
    "email_claim": "email",
    "name_claim": "name",
    "roles_claim": "resource_access.${client_id}.roles",
    "superuser_roles": ["baserow-superusers"],
    "staff_roles": ["baserow-staff"],
    "workspace_mappings": [
      { "client_role": "eng-leads", "workspace": 1, "permissions": "ADMIN" },
      { "client_role": "eng", "workspace": 1, "permissions": "MEMBER" },
      { "client_role": "eng-readonly", "workspace": 1, "permissions": "MEMBER", "role": "Reader" },
      { "client_role": "finance", "workspace": 2, "permissions": "MEMBER", "role": "Data editor" },
      { "client_role": "portal-builders", "workspace": 3, "permissions": "MEMBER", "role": "App builder" }
    ],
    "strict_membership": true,
    "require_verified_email": true,
    "session_lifetime_minutes": 480
  },
  {
    "name": "partners",
    "display_name": "Partner login",
    "issuer": "https://idp.partners.example.org/application/o/baserow/",
    "client_id": "baserow-partners",
    "client_secret": "change-me-partner-secret",
    "scopes": ["openid", "email", "profile"],
    "email_claim": "email",
    "name_claim": "name",
    "roles_claim": "groups",
    "superuser_roles": [],
    "staff_roles": [],
    "workspace_mappings": [
      { "client_role": "partner-ops", "workspace": 3, "permissions": "MEMBER", "role": "Automation operator" },
      { "client_role": "partner-viewers", "workspace": 2, "permissions": "MEMBER", "role": "Reader" }
    ],
    "strict_membership": true,
    "require_verified_email": true,
    "session_lifetime_minutes": 240
  }
]
```

Notes on this configuration:

* A user holding both `eng-leads` and `eng` is an Engineering `ADMIN` — `ADMIN` wins.
* `eng-readonly` plus `eng` in the same token is a configuration smell: the first matching
  `MEMBER` mapping in list order wins, so the user becomes an unrestricted member. Keep
  profiles for one workspace mutually exclusive in the IdP.
* The `partners` provider maps no global roles, so it never makes anyone staff, and it
  never revokes a staff flag granted through `rhbk` either — only configured dimensions
  are reconciled.
* Both providers use `strict_membership`, so each only revokes the memberships it created
  itself.

`BASEROW_ROLES` — every role referenced above, per workspace:

```json
[
  {
    "workspace": 1,
    "name": "Reader",
    "operations": [
      "workspace.read",
      "database.table.read",
      "database.table.field.read",
      "database.table.read_row",
      "database.table.view.read"
    ]
  },
  {
    "workspace": 2,
    "name": "Reader",
    "operations": [
      "workspace.read",
      "database.table.read",
      "database.table.field.read",
      "database.table.read_row",
      "database.table.view.read"
    ]
  },
  {
    "workspace": 2,
    "name": "Data editor",
    "operations": [
      "workspace.read",
      "database.table.read",
      "database.table.field.read",
      "database.table.view.read",
      "database.table.read_row",
      "database.table.create_row",
      "database.table.update_row",
      "database.table.delete_row"
    ]
  },
  {
    "workspace": 3,
    "name": "App builder",
    "operations": [
      "workspace.read",
      "database.table.read",
      "database.table.field.read",
      "database.table.read_row",
      "database.table.view.read",
      "builder.create_page",
      "builder.page.read",
      "builder.page.update",
      "builder.page.delete",
      "builder.page.create_element",
      "builder.page.element.read",
      "builder.page.element.update",
      "builder.page.element.delete"
    ]
  },
  {
    "workspace": 3,
    "name": "Automation operator",
    "operations": [
      "workspace.read",
      "database.table.read",
      "database.table.field.read",
      "database.table.read_row",
      "automation.create_workflow",
      "automation.workflow.read",
      "automation.workflow.update",
      "automation.workflow.delete",
      "automation.workflow.create_node",
      "automation.node.read",
      "automation.node.update",
      "automation.node.delete"
    ]
  }
]
```

A role is resolved per workspace, so `Reader` is declared once for workspace 1 and once
for workspace 2.

Rollout order:

1. Deploy with `BASEROW_ROLES` set and restart.
2. Create the workspaces (or confirm their ids) and run `sync_roles`.
3. Create the roles and assignments in each IdP.
4. Set `BASEROW_OIDC_PROVIDERS` and restart.
5. Sign in with one test user per profile, plus one with no mapped role (must be refused).

## Passing the configuration to Baserow

The values are JSON, so the only difficulty is quoting. Store them compacted to one line
where the format requires it, and keep secrets out of version control.

### `docker run`

`--env-file` takes each value literally up to the end of the line — no quotes, no line
breaks:

```bash
# baserow-sso.env
BASEROW_OIDC_PROVIDERS=[{"name":"rhbk","display_name":"Company SSO","issuer":"https://keycloak.example.com/realms/main","client_id":"baserow","client_secret":"change-me","staff_roles":["baserow-staff"],"workspace_mappings":[{"client_role":"eng","workspace":1,"permissions":"MEMBER"}]}]
BASEROW_ROLES=[{"workspace":1,"name":"Reader","operations":["workspace.read","database.table.read"]}]
BASEROW_OIDC_ONLY=true
```

```bash
docker run -d --name baserow \
  -e BASEROW_PUBLIC_URL=https://baserow.example.com \
  --env-file baserow-sso.env \
  -v baserow_data:/baserow/data -p 80:80 -p 443:443 \
  ghcr.io/carneirofc/baserow/baserow:latest
```

Compact a pretty-printed file with `jq -c . providers.json`.

### Docker Compose

The root [`docker-compose.yaml`](../../docker-compose.yaml) passes `BASEROW_OIDC_PROVIDERS`,
`BASEROW_OIDC_ONLY` and `BASEROW_ROLES` through from `.env`. Wrap each JSON value in
single quotes on one line:

```bash
# .env
BASEROW_OIDC_PROVIDERS='[{"name":"rhbk","issuer":"https://keycloak.example.com/realms/main","client_id":"baserow","client_secret":"change-me","staff_roles":["baserow-staff"]}]'
BASEROW_ROLES='[]'
BASEROW_OIDC_ONLY=true
```

Then `docker compose up -d` to recreate the containers with the new values.

### Helm

Set the variables through `extraEnv`; a block scalar keeps the JSON readable:

```yaml
extraEnv:
  BASEROW_OIDC_ONLY: "true"
  BASEROW_OIDC_PROVIDERS: |
    [{"name": "rhbk", "display_name": "Company SSO",
      "issuer": "https://keycloak.example.com/realms/main",
      "client_id": "baserow", "client_secret": "change-me",
      "staff_roles": ["baserow-staff"],
      "workspace_mappings": [
        {"client_role": "eng", "workspace": 1, "permissions": "MEMBER"}]}]
  BASEROW_ROLES: |
    [{"workspace": 1, "name": "Reader",
      "operations": ["workspace.read", "database.table.read"]}]
```

> `extraEnv` is rendered into the chart's ConfigMap, which is not encrypted, and
> `client_secret` lives inside the JSON. Restrict who can read ConfigMaps in the
> namespace, keep the values file out of version control (or encrypt it, for example with
> SOPS), and rotate the secret if it leaks. The pods pick up changes on `helm upgrade`.

## Configuring RHBK/Keycloak

Condensed setup for Red Hat build of Keycloak and upstream Keycloak (same console paths).
The [full RHBK/Keycloak guide](sso-rhbk-keycloak.md) walks through each screen, and covers
onboarding and offboarding, secret rotation, hardening, and a declarative realm import.

The issuer is `https://<keycloak-host>/realms/<realm>`.

1. **Create the client.** **Clients → Create client**:
   * Client type `OpenID Connect`, Client ID `baserow`.
   * **Client authentication** on; **Standard flow** on, other flows off.
   * **Valid redirect URIs**: `https://baserow.example.com/api/sso/oidc/callback/rhbk/`
     (`rhbk` = provider `name`).
   * **Advanced → Advanced settings → Proof Key for Code Exchange Code Challenge Method**:
     `S256`.
   * Copy the secret from **Credentials**.
2. **Create client roles.** **Clients → baserow → Roles → Create role**, one per profile:
   `baserow-superusers`, `baserow-staff`, `eng-leads`, `eng`, `eng-readonly`, `finance`,
   `portal-builders`. Baserow reads **client** roles by default, not realm roles.
3. **Assign roles through groups.** **Groups → Create group** (e.g. `baserow-eng`), then
   **Role mapping → Assign role → Filter by clients** and pick the `baserow` roles — the
   default filter lists only realm roles. Add users under **Members**.
4. **Put client roles in the ID token and userinfo.** Keycloak's built-in client roles
   mapper adds them to the access token only, and Baserow reads the ID token and
   userinfo. On **Clients → baserow → Client scopes → `baserow-dedicated` → Add mapper →
   By configuration → User Client Role**:

   | Field | Value |
   | --- | --- |
   | Name | `baserow client roles` |
   | Client ID | `baserow` |
   | Token Claim Name | `resource_access.${client_id}.roles` |
   | Claim JSON Type | `String` |
   | Multivalued | On |
   | Add to ID token | **On** |
   | Add to userinfo | **On** |
   | Add to access token | On |

   If **Full scope allowed** is off on the client, also add the roles under its **Scope**
   tab.
5. **Verify the claim.** **Clients → baserow → Client scopes → Evaluate**, pick a user,
   open **Generated ID token**, and look for:

   ```json
   "resource_access": { "baserow": { "roles": ["eng"] } }
   ```

6. **Check email verification.** Users need `email_verified: true`. For LDAP/AD
   federation, enable **Trust Email** on the user federation provider; otherwise verify
   users' emails or set `require_verified_email: false`.
7. **Keep self-registration off** in **Realm settings → Login**, since Baserow links
   accounts by email.
8. **Configure Baserow** with the `rhbk` provider from the
   [complete example](#complete-example) (the default `roles_claim` already matches step 4),
   declare `BASEROW_ROLES`, restart, and run `sync_roles`.
9. **Test** with one user per group and one user in no group — the latter must land on
   `/login?error=errorNoMappedRole` and no account may appear in the admin area.

To map **realm roles** instead, set `"roles_claim": "realm_access.roles"` and enable
**Add to ID token** / **Add to userinfo** on the realm roles mapper. To map Keycloak
**groups** directly, add a **Group Membership** mapper with Token Claim Name `groups`,
**Full group path** off, ID token and userinfo on, and set `"roles_claim": "groups"`.

## Login error codes

A failed login redirects to `/login?error=<code>`, and the backend log has details.

| Code | Cause | Fix |
| --- | --- | --- |
| `errorNoMappedRole` | The provider maps roles and the user holds none of them — or the roles never reached Baserow. | Check the token contents (for Keycloak: **Evaluate**, step 5 above); check `roles_claim`; assign the user a mapped role. |
| `errorEmailNotVerified` | `require_verified_email` is on and `email_verified` is not `true`. | Verify the email in the IdP, trust federated emails, or set `require_verified_email: false`. |
| `errorAuthFlowError` | Discovery or JWKS unreachable; token signature/issuer/audience/nonce check failed; userinfo `sub` mismatch; no email returned; `state`/PKCE mismatch; the IdP returned no code. | Read the backend log. Check network and TLS trust to the issuer, the exact `issuer` string, `client_id`, the redirect URI, and the client's PKCE method. |
| `errorProviderDoesNotExist` | The callback or login URL names a provider not in `BASEROW_OIDC_PROVIDERS`. | Match the redirect URI's `<name>` to the provider `name`; restart after config changes. |
| `errorDifferentProvider` | An account with this email exists under a different sign-in method. | Expected protection. Link the account with the `link_oidc_account` command, or set `link_existing_accounts` on the provider. See [Recovering locked-out accounts](#recovering-locked-out-accounts). |
| `errorUserDeactivated` | The Baserow account is deactivated. | Reactivate it in the admin area. |
| `errorWorkspaceInvitationEmailMismatch` | The user followed a workspace invitation addressed to another email. | Sign in with the invited address, or send a new invitation. |
| `errorSignupDisabled` | The signup layer refused to create the account. SSO provisioning normally bypasses the signup setting, so this indicates an unusual flow. | Check the backend log. |

## Recovering locked-out accounts

`errorDifferentProvider` means the account exists but is not linked to this provider:
it was created with a password or another provider, or the provider's `name` changed
(each `name` has its own links, so a rename locks every user out). Link it with the
`link_oidc_account` management command — no restart needed:

```sh
# Docker Compose (all-in-one image: docker exec baserow ./baserow.sh backend-cmd manage ...)
docker compose exec backend /baserow/backend/docker/docker-entrypoint.sh manage link_oidc_account list alice@example.com
docker compose exec backend /baserow/backend/docker/docker-entrypoint.sh manage link_oidc_account link keycloak --email alice@example.com
# after renaming a provider from "old-name" to "keycloak"
docker compose exec backend /baserow/backend/docker/docker-entrypoint.sh manage link_oidc_account link keycloak --from-provider old-name
docker compose exec backend /baserow/backend/docker/docker-entrypoint.sh manage link_oidc_account unlink keycloak --email alice@example.com
```

`link` requires the provider to be in `BASEROW_OIDC_PROVIDERS` and works for staff
accounts too. To link many regular accounts without operator action, set
`link_existing_accounts: true` on the provider instead.

## Security notes

* **Accounts are linked by email.** Anyone who can obtain a verified token for an address
  can sign in as the Baserow account with that address. Keep IdP self-registration off,
  keep `require_verified_email` on unless the IdP's addresses are authoritative, and leave
  `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT` unset.
* **`link_existing_accounts` trusts the IdP with existing accounts.** Enable it only on an
  IdP whose verified emails are authoritative. Staff and superuser accounts are never
  linked automatically; link them with `link_oidc_account`.
* **Deny by default only applies when something is mapped.** A provider with no
  `superuser_roles`, `staff_roles` or `workspace_mappings` lets every user of that IdP
  create an account.
* **Prefer granular roles over workspace `ADMIN`.** A workspace admin can invite anyone and
  change members' permissions, bypassing roles entirely.
* **Keep a break-glass admin.** A local staff account that signs in with a password is
  never touched by SSO reconciliation, and still works under `BASEROW_OIDC_ONLY`.
* **Set the instance's email verification to "no verification"** (admin settings).
  SSO-provisioned accounts start unverified, and `recommended`/`enforced` would email users
  about an address the IdP already vouches for.
* **Protect the secret.** `client_secret` sits inside `BASEROW_OIDC_PROVIDERS`; treat the
  whole variable as a secret wherever it is stored.

## Troubleshooting

1. **Backend will not start** — read the `ImproperlyConfigured` message; it names the
   provider index and key (for example
   `BASEROW_OIDC_PROVIDERS[0].workspace_mappings[1]: 'workspace' must be an integer workspace id.`).
   Validate syntax with `jq . <<< "$BASEROW_OIDC_PROVIDERS"`.
2. **Config change ignored** — restart the backend and workers.
3. **Issuer reachable?** From inside the backend container:

   ```bash
   curl -fsS "https://keycloak.example.com/realms/main/.well-known/openid-configuration"
   ```

   A failure here is DNS, network or TLS trust, not Baserow configuration.
4. **Roles in the token?** Inspect the ID token and userinfo in the IdP (Keycloak:
   **Evaluate**) and confirm the path matches `roles_claim`.
5. **Signed in but no workspace** — the role string does not match `client_role` exactly,
   or the workspace id does not exist (backend warning: `maps to unknown workspace`).
6. **Membership refused** — the mapping's `role` is not in the database for that workspace
   (backend error: `maps workspace <id> to unknown role`). Declare it in `BASEROW_ROLES`
   and run `sync_roles`.
7. **Role grants too little** — an operation was misspelled (backend warning:
   `lists operation ... which is not controllable by a role`), or a prerequisite read
   operation is missing.
8. **Access not revoked** — revocation needs `strict_membership: true` and a new login;
   hand-added memberships and a workspace's last admin are never revoked.

## Related

* [Single sign-on with RHBK/Keycloak](sso-rhbk-keycloak.md) — detailed Keycloak guide.
* [Configuration](configuration.md) — every environment variable.
* [Turning application types off instance-wide](instance-settings.md).
* [Installing with Helm](install-with-helm.md).
