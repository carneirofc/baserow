# Single sign-on with Red Hat build of Keycloak (RHBK)

This guide configures Baserow so that **every kind of access is decided by Keycloak
client roles**: who is a Baserow administrator, who is a member of which workspace, and
what they may do inside it. A user holding none of the mapped client roles is refused at
login and no account is created for them.

It applies equally to upstream Keycloak and the Red Hat build (RHBK); the admin console
paths are the same.

## 1. Create the client

In the realm you want Baserow to use:

1. **Clients → Create client**, client type `OpenID Connect`, Client ID `baserow`.
2. Enable **Client authentication** (Baserow is a confidential client and uses a secret).
3. Under **Authentication flow**, keep **Standard flow** enabled; the others are unused.
4. Set **Valid redirect URIs** to
   `<BASEROW_PUBLIC_URL>/api/sso/oidc/callback/<name>/`, where `<name>` is the provider
   `name` you will put in `BASEROW_OIDC_PROVIDERS` — for example
   `https://baserow.example.com/api/sso/oidc/callback/rhbk/`.
5. Copy the secret from the client's **Credentials** tab.

## 2. Define the client roles

Baserow reads **client** roles (`resource_access.<client_id>.roles`), not realm roles.
On the `baserow` client, open **Roles → Create role** and add one role per profile you
want to express, for example:

| Client role | What Baserow will do with it |
| --- | --- |
| `baserow-admins` | grant global superuser |
| `baserow-staff` | grant global staff |
| `engineering` | full member of workspace 1 |
| `analysts` | member of workspace 1, restricted to the `Reader` role |

Assign them to users or, preferably, to Keycloak groups whose members inherit them
(**Groups → *group* → Role mapping → Assign role → Filter by clients**).

## 3. Put the client roles into the ID token and userinfo

**This is the step that is easy to miss.** Keycloak's built-in `client roles` mapper adds
`resource_access.<client_id>.roles` to the **access token only** — *Add to ID token* and
*Add to userinfo* are off by default, and Baserow reads the ID token and the userinfo
response. Without this step the user appears to hold no roles at all and every login is
refused.

That built-in mapper lives in the realm-wide `roles` client scope, so editing it changes
every client in the realm. Add a mapper on the Baserow client's **dedicated** scope
instead:

1. **Clients → baserow → Client scopes → `baserow-dedicated` → Add mapper → By
   configuration → User Client Role**.
2. Configure it:
   - **Name**: `baserow client roles`
   - **Client ID**: `baserow` (restricts the claim to this client's roles)
   - **Token Claim Name**: `resource_access.${client_id}.roles`
   - **Claim JSON Type**: `String`
   - **Multivalued**: On
   - **Add to ID token**: **On**
   - **Add to userinfo**: **On**
   - **Add to access token**: On (harmless; leave as it comes)

Baserow only needs one of the two token types to carry the claim — it reads both and
takes the union — but enabling both is the most forgiving configuration.

> If the client has **Full scope allowed** turned off, also add the roles you defined to
> the client's **Scope** tab, or Keycloak will filter them out of the token.

### Verifying the claim

Use **Clients → baserow → Client scopes → Evaluate**, pick a user, and look at
*Generated ID token*. You should see:

```json
"resource_access": {
  "baserow": {
    "roles": ["analysts"]
  }
}
```

If `resource_access` is missing from the ID token, the mapper's *Add to ID token* toggle
is still off.

## 4. Declare the granular roles Baserow will grant

A workspace mapping can restrict a member to a named set of operations. Declare those
roles in `BASEROW_ROLES`, one entry per workspace and role name:

```bash
BASEROW_ROLES='[
  {
    "workspace": 1,
    "name": "Reader",
    "operations": ["database.table.read"]
  }
]'
```

The declaration is the source of truth and is reconciled into the database after every
migrate. Workspaces are usually created *after* a deploy, so run the reconcile again once
the workspace exists:

```bash
# all-in-one image
docker exec baserow ./baserow.sh backend-cmd manage sync_roles
# from a development checkout
just backend manage sync_roles
```

Roles that are no longer declared are left in place, because members may still be
assigned to them.

## 5. Configure the provider

```bash
BASEROW_OIDC_PROVIDERS='[
  {
    "name": "rhbk",
    "display_name": "Company SSO",
    "issuer": "https://keycloak.example.com/realms/main",
    "client_id": "baserow",
    "client_secret": "the-secret",

    "superuser_roles": ["baserow-admins"],
    "staff_roles": ["baserow-staff"],

    "workspace_mappings": [
      { "client_role": "engineering", "workspace": 1, "permissions": "MEMBER" },
      { "client_role": "analysts", "workspace": 1, "permissions": "MEMBER",
        "role": "Reader" }
    ],

    "strict_membership": true
  }
]'
```

`roles_claim` is omitted above because its default is already
`resource_access.${client_id}.roles`, with `${client_id}` replaced by this provider's
`client_id`. Override it to read realm roles (`realm_access.roles`) or a custom mapper's
claim instead. A literal dot inside a claim name is escaped as `\.`.

The full key reference lives in [configuration.md](configuration.md).

## How access is decided on each login

1. Baserow reads the client roles from the ID token and the userinfo response and unions
   them.
2. If the provider maps any client role and the user holds none of them, the login is
   refused with `errorNoMappedRole` — **before** any account is provisioned.
3. `staff_roles` / `superuser_roles` are reconciled onto the user: granted when held,
   revoked when not. Only the dimensions you configure are touched.
4. Each matching workspace mapping is applied. The sync is authoritative for the
   workspaces it maps, writing both the membership permissions and the granular role, so
   removing `role` from a mapping restores full member access on the next login.
5. With `strict_membership: true`, memberships this sync previously created are revoked
   once the user loses the mapped client role. Memberships added by hand are never
   tracked and never revoked.

Because all of this runs only during an OIDC login, a local break-glass administrator who
never signs in through Keycloak is never modified.

## Locking the instance down

Set `BASEROW_OIDC_ONLY=true` to disable password signup and refuse password login for
non-staff accounts. A staff/superuser account can still use the password form (via
"display password login" on the login page) so an outage of the IdP cannot lock you out
of your own instance. Create that break-glass account before turning this on.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Every login redirects to `/login?error=errorNoMappedRole` | The client-roles mapper is not enabled on the ID token *and* userinfo, or the user holds none of the mapped client roles. Check **Evaluate** (step 3). |
| The user signs in but lands in no workspace | The client role in `workspace_mappings[].client_role` does not match the Keycloak role name exactly, or `workspace` points at an id that does not exist — the backend logs a warning naming it. |
| The user is refused a workspace they should get | The mapping names a `role` that is not in the database. Declare it in `BASEROW_ROLES` and run `sync_roles`; Baserow fails closed rather than granting unrestricted access. |
| The backend refuses to start after an upgrade | The provider JSON still uses the retired `groups_claim` / `staff_groups` / `superuser_groups` keys, or the old `workspace_mappings` shape. The error names the replacement for each. |
| `errorDifferentProvider` on login | The email already exists under another authentication method. See `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT`. |
