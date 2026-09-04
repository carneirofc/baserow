# Single sign-on with Red Hat build of Keycloak (RHBK)

This guide configures Baserow so that **every kind of access is decided by Keycloak
client roles**: who administers the instance, who is a member of which workspace, and what
they may do inside it. A user holding none of the mapped client roles is refused at login
and no account is created for them.

It then covers how to run that setup day to day — onboarding, granting access, offboarding
and rotating the secret — and how to prove the integration works before handing it to
users.

It applies equally to upstream Keycloak and the Red Hat build (RHBK); the admin console
paths are the same.

## What this guide assumes

Deploying Keycloak itself is out of scope. Before you start you need:

* A **running** Keycloak/RHBK instance, reachable over HTTPS from the Baserow backend
  (the backend fetches the discovery document and the JWKS itself, server to server).
* An account that can manage clients, roles, groups and users in the target realm.
* The realm you want Baserow to use, decided. Its issuer URL is
  `https://<keycloak-host>/realms/<realm>` — that exact string is what goes in `issuer`
  below, and Baserow appends `/.well-known/openid-configuration` to it to discover the
  rest.
* Baserow's own public URL, since it determines the redirect URI you register in step 1.

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

Pick the names deliberately: they are the contract between the two systems, and renaming
one later means editing `BASEROW_OIDC_PROVIDERS` and restarting the backend.

### Administrator means the whole instance

Baserow has two separate notions of privilege, and this guide only ever grants the first
one through SSO:

* **Global** — `is_staff` / `is_superuser`. Instance-wide authority: the admin area,
  instance settings, every workspace. Granted by `staff_roles` / `superuser_roles`.
* **Workspace-scoped** — a member's `ADMIN` or `MEMBER` permissions inside one workspace.
  `ADMIN` there can invite and remove members and delete that workspace, but has no
  authority anywhere else.

Throughout this guide **"administrator" means the global one**, and every workspace
mapping grants `MEMBER`. What varies between workspace profiles is the granular role, not
the membership level.

`workspace_mappings` does accept `"permissions": "ADMIN"` (see
[configuration.md](configuration.md)) — this setup just does not use it. It is a poor fit
for role-driven access anyway: a workspace admin bypasses the granular role permission
manager, so Baserow refuses to combine `ADMIN` with a `role`.

## 3. Assign the roles through groups

You can assign client roles directly to users, but groups are the shape worth building.
Baserow reconciles access on **every** login, so one group membership becomes the single
lever that both grants and revokes a person's access.

1. **Groups → Create group**, one per profile — for example `baserow-engineering`.
2. Open the group, go to **Role mapping → Assign role**, then switch the filter to
   **Filter by clients** and pick the `baserow` roles. This filter is the step people
   miss: the default view lists only realm roles, and Baserow ignores those.
3. Add users to the group under its **Members** tab.

From then on, onboarding and offboarding are group membership changes and nothing else.

## 4. Put the client roles into the ID token and userinfo

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

The dedicated scope is always applied, whatever scopes the client asks for, so there is
nothing to add to the provider's `scopes` list to make this mapper fire.

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

## 5. Declare the granular roles Baserow will grant

A workspace mapping can restrict a member to a named set of operations. Declare those
roles in `BASEROW_ROLES`, one entry per workspace and role name.

Steps 5 and 6 below configure one worked scenario. It is worth reading as a whole before
transcribing it, because the two blocks reference each other by workspace id and role name:

| Keycloak client role | Grants | Workspace | Level | Granular role |
| --- | --- | --- | --- | --- |
| `baserow-admins` | global superuser | — (instance-wide) | — | — |
| `baserow-staff` | global staff | — (instance-wide) | — | — |
| `engineering` | workspace membership | `Engineering` (id `1`) | `MEMBER` | none — full member |
| `analysts` | workspace membership | `Engineering` (id `1`) | `MEMBER` | `Reader` |

```jsonc
BASEROW_ROLES='[
  {
    // The numeric id of the workspace this role belongs to — here, "Engineering".
    // A role is resolved per workspace, so this must match the `workspace` of the
    // mapping that names it in step 7.
    "workspace": 1,

    // The name a workspace mapping refers to with its `role` key.
    "name": "Reader",

    // Exactly what a member holding this role may do. Anything not listed is denied.
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

## 6. Find the workspace ids

Mappings key off the **numeric workspace id**, never the workspace name. Both
`workspace_mappings[].workspace` and `BASEROW_ROLES[].workspace` must be integers. Three
ways to find the id of a workspace:

* **Admin area → Workspaces** (`/admin/workspaces`, staff only). The list is searchable
  and sortable by `id`.
* **The API** — `GET /api/admin/workspaces/` returns `id` and `name` for every workspace.
  It needs a token belonging to a staff account.
* **The workspace URL** — open the workspace in Baserow and read it off the address bar,
  which is `/workspace/<id>`.

> Ids are assigned per database, so they differ between environments. The same
> `BASEROW_OIDC_PROVIDERS` value copied from staging to production will silently grant
> access to whichever workspaces happen to hold those ids there. Re-check the ids after
> any copy.

A mapping naming a workspace id that does not exist is skipped with a warning in the
backend log rather than refused at startup — the user simply signs in with no membership.

## 7. Configure the provider

```jsonc
BASEROW_OIDC_PROVIDERS='[
  {
    // Url-safe slug. It appears in the callback URL you registered in step 1:
    // <BASEROW_PUBLIC_URL>/api/sso/oidc/callback/rhbk/
    "name": "rhbk",

    // The label on the login button.
    "display_name": "Company SSO",

    // https://<keycloak-host>/realms/<realm>. Baserow appends
    // /.well-known/openid-configuration to discover the rest.
    "issuer": "https://keycloak.example.com/realms/main",

    "client_id": "baserow",
    "client_secret": "the-secret",

    // --- Instance-wide authority. Not tied to any workspace. ---
    "superuser_roles": ["baserow-admins"],
    "staff_roles": ["baserow-staff"],

    // --- Workspace membership. One entry per client role, per workspace. ---
    "workspace_mappings": [
      {
        "client_role": "engineering", // the Keycloak client role from step 2
        "workspace": 1,               // numeric id of "Engineering" (see step 6)
        "permissions": "MEMBER"       // membership level; no `role`, so a full member
      },
      {
        "client_role": "analysts",
        "workspace": 1,               // the same workspace...
        "permissions": "MEMBER",
        "role": "Reader"              // ...but restricted to the BASEROW_ROLES entry
                                      // named "Reader" for workspace 1
      }
    ],

    // Revoke the memberships this sync created once the user loses the client role
    // that granted them. Memberships added by hand are never touched.
    "strict_membership": true
  }
]'
```

`roles_claim` is omitted above because its default is already
`resource_access.${client_id}.roles`, with `${client_id}` replaced by this provider's
`client_id`. Override it to read realm roles (`realm_access.roles`) or a custom mapper's
claim instead. A literal dot inside a claim name is escaped as `\.`.

The full key reference lives in [configuration.md](configuration.md).

> `BASEROW_OIDC_PROVIDERS` and `BASEROW_ROLES` are parsed and validated once, at startup.
> **Every change to either needs a backend restart** before it takes effect, and an
> invalid value stops the backend from starting rather than failing later at login.

## 8. Verify the integration end to end

Work through these in order, so a failure tells you which layer is wrong.

1. **The claim is in the token.** Use **Evaluate** as described in step 4. If the roles
   are missing here, nothing downstream can work.
2. **Baserow can reach the issuer.** From the backend container:

   ```bash
   curl -fsS "https://keycloak.example.com/realms/main/.well-known/openid-configuration"
   ```

   A failure here is network, DNS or TLS trust — not configuration.
3. **A mapped user gets the right access.** Log in as a test user holding exactly one
   mapped client role. They should land in the expected workspace, with the expected
   permissions, and — if the mapping names a granular role — be unable to perform
   operations outside it.
4. **An unmapped user is refused.** Log in as a test user holding none of the mapped
   roles. Baserow must redirect to `/login?error=errorNoMappedRole`, and **no account may
   exist for them afterwards**. Check the admin area's user list: a user appearing there means
   the provider maps no client role at all, so the gate is inactive.

## How access is decided on each login

1. Baserow reads the client roles from the ID token and the userinfo response and unions
   them.
2. If the provider maps any client role and the user holds none of them, the login is
   refused with `errorNoMappedRole` — **before** any account is provisioned.
3. `staff_roles` / `superuser_roles` are reconciled onto the user: granted when held,
   revoked when not. Only the dimensions you configure are touched.
4. Each matching workspace mapping is applied, as a `MEMBER` of that workspace. The sync
   is authoritative for the workspaces it maps, writing both the membership level and the
   granular role, so removing `role` from a mapping restores full member access on the
   next login. What distinguishes one workspace profile from another is the granular role,
   not the membership level.
5. With `strict_membership: true`, memberships this sync previously created are revoked
   once the user loses the mapped client role. Memberships added by hand are never
   tracked and never revoked.

Because all of this runs only during an OIDC login, a local break-glass administrator who
never signs in through Keycloak is never modified.

## Day-to-day operations

Everything below reconciles on the user's **next login**. Nothing in Keycloak reaches into
a session that is already open.

### Onboard someone

Add them to the Keycloak group from step 3. There is nothing to do in Baserow — the
account is provisioned on their first login, with the memberships their roles imply.

### Give someone access to another workspace

Add a `workspace_mappings` entry for the client role and the workspace id, restart the
backend, and have the user log in again.

### Add a new restricted profile

Order matters, because an unknown granular role fails closed and the membership is
refused outright rather than granted unrestricted:

1. Add the role to `BASEROW_ROLES` and restart the backend.
2. Run `sync_roles` so the role exists in the database.
3. Create the client role in Keycloak and assign it to a group.
4. Add the `workspace_mappings` entry naming both the `client_role` and the `role`, then
   restart.

### Promote or demote a global administrator

This is instance-wide authority, not access to one workspace. Add or remove the client
role listed in `staff_roles` / `superuser_roles`. The flags are reconciled on the next
login — including revocation, so a demotion takes effect the next time they sign in.

### Give a workspace an administrator

SSO only ever grants `MEMBER`, so a workspace's own `ADMIN` never arrives from Keycloak.
It is whoever created the workspace, or someone promoted by hand from the workspace's
members list. Do not wait for a client role to produce one.

### Offboard someone

Remove the client roles, or remove them from the group. With `strict_membership: true`
the memberships this sync created are revoked the next time they log in.

> Removing a role does **not** end an active session, and a user who simply never logs in
> again keeps the memberships they already have. To cut access immediately, disable or
> delete the user in Keycloak, and deactivate the account from Baserow's admin area if
> they must lose access to data they can already see.

### Rotate the client secret

Regenerate it under **Clients → baserow → Credentials**, update `client_secret` in
`BASEROW_OIDC_PROVIDERS`, and restart the backend. Logins fail in between, so do it in a
window you can tolerate.

## Hardening

### The realm

Baserow matches an incoming SSO identity to an existing account **by email address**. Two
consequences:

* Keep realm self-registration disabled, or make sure the email address on an account is
  authoritative (for example because users come from LDAP/AD federation). A realm where a
  stranger can self-register an arbitrary address is a realm where they can attempt to
  land on someone else's Baserow account.
* Leave `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT` unset. By default, an
  account created through a different authentication method cannot be taken over through
  this provider — Baserow refuses with `errorDifferentProvider`. That env var removes the
  check.

### The Baserow instance

Set the instance's email verification setting to **no verification** (admin settings).
SSO-provisioned accounts are created with their email marked unverified, so `recommended`
or `enforced` makes Baserow send a verification mail for an address Keycloak already owns.

Set `BASEROW_OIDC_ONLY=true` to disable password signup and refuse password login for
non-staff accounts. A staff/superuser account can still use the password form (via
"display password login" on the login page) so an outage of the IdP cannot lock you out
of your own instance. **Create that break-glass account before turning this on.**

### Reduce the surface: turn off the application types you don't use

Everything above decides *who* gets in and *which* workspaces they land in. It says
nothing about *what kinds of application* the instance offers. If your deployment only
ever uses databases, leave the application builder, dashboards and automations switched
off rather than relying on nobody creating one.

The switches are in the admin area under **Settings → Application features**, and they are
instance-wide in the same sense as the global staff/superuser flags above — the same
distinction the [Administrator means the whole instance](#administrator-means-the-whole-instance)
section draws. A disabled type cannot be created, and its existing applications are hidden
and refused; the data is not deleted, and re-enabling restores it. This is deliberately
not something Keycloak can drive: it is a property of the instance, not of a user or a
workspace, so no client role or `workspace_mappings` entry affects it.

See [Turning application types off instance-wide](instance-settings.md) for what each
toggle covers and how to set it through the API.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Every login redirects to `/login?error=errorNoMappedRole` | The client-roles mapper is not enabled on the ID token *and* userinfo, or the user holds none of the mapped client roles. Check **Evaluate** (step 4). |
| The user signs in but lands in no workspace | The client role in `workspace_mappings[].client_role` does not match the Keycloak role name exactly, or `workspace` points at an id that does not exist — the backend logs a warning naming it. |
| The user is refused a workspace they should get | The mapping names a `role` that is not in the database. Declare it in `BASEROW_ROLES` and run `sync_roles`; Baserow fails closed rather than granting unrestricted access. |
| A configuration change had no effect | The provider JSON is read at startup. Restart the backend. |
| The backend refuses to start after an upgrade | The provider JSON still uses the retired `groups_claim` / `staff_groups` / `superuser_groups` keys, or the old `workspace_mappings` shape. The error names the replacement for each. |
| `errorAuthFlowError` immediately after the Keycloak redirect | The redirect URI registered on the client does not match `<BASEROW_PUBLIC_URL>/api/sso/oidc/callback/<name>/`, or the backend cannot reach the issuer. Check the backend log and step 8.2. |
| `errorDifferentProvider` on login | The email already exists under another authentication method. See `BASEROW_ALLOW_MULTIPLE_SSO_PROVIDERS_FOR_SAME_ACCOUNT`. |

## Appendix: configuring the realm declaratively

The admin console steps above are the authoritative path. This appendix reproduces the
same realm-side configuration as a JSON representation, for rebuilding a realm or keeping
it in version control.

It creates exactly three things, matching steps 1, 2 and 4:

* the confidential `baserow` client, with the redirect URI from step 1;
* the four client roles from step 2 — two that map to instance-wide authority
  (`baserow-admins`, `baserow-staff`) and two that map to workspace membership
  (`engineering`, `analysts`);
* the `oidc-usermodel-client-role-mapper` from step 4, emitting
  `resource_access.baserow.roles` into the ID token, the access token and userinfo.

It deliberately does **not** contain the workspace ids or membership levels — those live
only in Baserow's `BASEROW_OIDC_PROVIDERS`, because Keycloak has no notion of a Baserow
workspace. The client role name is the entire contract between the two files.

Unlike the examples in steps 5 and 7, this block carries no `//` comments: it is pasted
into Keycloak's partial import and `kcadm.sh`, which accept strict JSON only.

> Keycloak's export format varies between versions. Treat this as a starting point:
> configure one realm through the console, then use **Realm settings → Action → Partial
> export** with clients included, and take the exported block as your source of truth.

```json
{
  "clients": [
    {
      "clientId": "baserow",
      "name": "Baserow",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": false,
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": false,
      "redirectUris": [
        "https://baserow.example.com/api/sso/oidc/callback/rhbk/"
      ],
      "fullScopeAllowed": true,
      "protocolMappers": [
        {
          "name": "baserow client roles",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-usermodel-client-role-mapper",
          "config": {
            "usermodel.clientRoleMapping.clientId": "baserow",
            "claim.name": "resource_access.${client_id}.roles",
            "jsonType.label": "String",
            "multivalued": "true",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "userinfo.token.claim": "true"
          }
        }
      ]
    }
  ],
  "roles": {
    "client": {
      "baserow": [
        { "name": "baserow-admins", "description": "Baserow global superuser" },
        { "name": "baserow-staff", "description": "Baserow global staff" },
        { "name": "engineering", "description": "Member of workspace 1" },
        { "name": "analysts", "description": "Reader in workspace 1" }
      ]
    }
  }
}
```

Apply it to a running instance in one of three ways:

1. **Admin console** — **Realm settings → Action → Partial import**, paste the JSON, and
   choose what to do about resources that already exist.
2. **`kcadm.sh`** — authenticate, then create the client from the file:

   ```bash
   kcadm.sh config credentials \
     --server https://keycloak.example.com \
     --realm master --user admin
   kcadm.sh create clients -r main -f baserow-client.json
   ```

3. **Operator-managed realms** — wrap the realm representation in a `KeycloakRealmImport`
   resource, in the same namespace as the `Keycloak` resource it names:

   ```yaml
   apiVersion: k8s.keycloak.org/v2beta1
   kind: KeycloakRealmImport
   metadata:
     name: baserow-realm
   spec:
     keycloakCRName: <name of the Keycloak resource>
     realm:
       realm: main
       enabled: true
       clients: [] # the clients block above
       roles: {}   # the roles block above
   ```

   This path only applies to a realm the Keycloak Operator manages; for any other
   instance use one of the first two.

Groups and their role mappings can be exported the same way, but group membership is
usually owned by your directory rather than by a committed file — keep users out of the
declarative realm unless you are building a throwaway environment.
