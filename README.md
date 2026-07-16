## Baserow FOSS fork: a no-code database, app builder and automation platform

This is a fork of [Baserow](https://baserow.io) with the proprietary editions removed,
intended as a clean open source starting point.

Upstream Baserow is open-core: most of it is MIT licensed, but the `premium/` and
`enterprise/` directories are covered by separate licenses that require a paid
subscription for production use and forbid redistribution. This fork deletes those
directories entirely, so **everything here is MIT licensed** (documentation under
CC BY-SA 4.0) and free for commercial and private use.

* A spreadsheet database hybrid combining ease of use and powerful data organization.
* Create applications and portals, and publish them on your own domain.
* Automate repetitive workflows with automations.
* Visualize your data with dashboards.
* Headless and API first.
* Self-hosted with no storage restrictions and no license checks.
* Uses popular frameworks and tools like [Django](https://www.djangoproject.com/),
  [Vue.js](https://vuejs.org/) and [PostgreSQL](https://www.postgresql.org/).

![Database screenshot](docs/assets/screenshot.png "Database screenshot")

![Form screenshot](docs/assets/screenshot_form.png "Form view screenshot")

![Application builder](docs/assets/screenshot_application_builder.png "Application builder screenshot")

![Automations](docs/assets/screenshot_automations.png "Automations screenshot")

![Dashboard](docs/assets/screenshot_dashboard.png "Dashboard screenshot")

## What this fork removes

Deleting the paid directories removes the features they implemented. What remains is the
full MIT core: databases, grid/gallery/form views, the application builder, automations,
dashboards, integrations, webhooks, the REST API and the plugin system.

Removed with `premium/`:
Kanban, calendar and timeline views; row comments; AI fields; JSON, XML, Excel and file
exports; personal views; row coloring; survey form mode; the premium admin panel.

Removed with `enterprise/`:
role-based access control; teams; SSO/SAML; audit log; field-level permissions; secure
file serve; data sync; the code runner; the AI assistant.

The plugin system is untouched, so these can be reimplemented as third party plugins.
Anything reimplemented here must be written from scratch — the removed code is not
licensed for reuse.

## Telemetry

This fork makes no outbound calls to Baserow B.V. or anyone else. The upstream
onboarding flow shipped a pre-checked box that sent your users' email, role, company
size and country to `api.baserow.io`; that has been removed.

Optional observability hooks remain, and are off unless you turn them on:

| Variable | Default | Effect |
| --- | --- | --- |
| `SENTRY_DSN` | unset | Error reporting, to the DSN you supply |
| `BASEROW_ENABLE_OTEL` | unset | OpenTelemetry traces, to the endpoint you supply |
| `POSTHOG_PROJECT_API_KEY` | unset | Product analytics, to the project you supply |

All three are FOSS clients and only ever report to endpoints you configure.

## Installation

The installation guides below are inherited from upstream and mostly still apply, but
note that the published `baserow/baserow` Docker images include the premium and
enterprise editions. To run this fork, build the images from this repository.

* [**Docker**](docs/installation/install-with-docker.md)
* [**Helm**](docs/installation/install-with-helm.md)
* [**Docker Compose**](docs/installation/install-with-docker-compose.md)
* [**Heroku**](docs/installation/install-on-heroku.md)
* [**Render**](docs/installation/install-on-render.md)
* [**Digital Ocean**](docs/installation/install-on-digital-ocean.md)
* [**AWS**](docs/installation/install-on-aws.md)
* [**Cloudron**](docs/installation/install-on-cloudron.md)
* [**Railway**](docs/installation/install-on-railway.md)

## Documentation

Documentation lives [in the repository](./docs/index.md). Upstream's hosted docs at
https://baserow.io/docs/index also cover the premium and enterprise features that this
fork does not ship.

## Development environment

```bash
git clone https://github.com/carneirofc/baserow.git
cd baserow

just dc-dev build --parallel
just dc-dev up -d
```

Visit [http://localhost:3000](http://localhost:3000) for a development build with hot
reloading. See [the development environment docs](./docs/development/development-environment.md)
for more detail.

## Meta

Baserow was created by Baserow B.V. - bram@baserow.io. This fork is not affiliated with
or endorsed by Baserow B.V. "Baserow" and the Baserow logo are trademarks of Baserow
B.V.; the MIT license covers the code, not the trademarks.

Distributed under the MIT license. See `LICENSE` for more information.

Upstream repository: https://github.com/baserow/baserow

The upstream changelog can be found [here](./changelog.md).
</content>
