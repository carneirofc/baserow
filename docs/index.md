# Table of contents

Saveroom is an open-source online database tool, a fork of Baserow. Users can use this no-code platform to
create a database without any technical experience. It lowers the barriers to app
creation so that anyone who can work with a spreadsheet can also create a database. The
interface looks a lot like a spreadsheet. Our goal is to provide a perfect and fast user
experience while keeping it easy for developers to write plugins and maintain the
codebase. The developer documentation contains several topics you might need as a
developer.

## Installation

You can easily self-host Saveroom by following one of the guides below:

* [Install with Docker](installation/install-with-docker.md): A step-by-step guide to
  install Saveroom using docker.
* [Install with Docker Compose](installation/install-with-docker-compose.md): A
  step-by-step guide to install Saveroom using Docker Compose.
* [Install on AWS](installation/install-on-aws.md): An overview of your options to 
  install Saveroom on AWS with two specific guides for ECS.
* [Install using Standalone images](installation/install-using-standalone-images.md): A
  general overview on how to run the Saveroom standalone service images with your own
  container orchestration software.
* [Install on Digital Ocean Apps](installation/install-on-digital-ocean.md):
  Instructions on how to install on Digital Ocean Apps platform.
* [Install on Railway](installation/install-on-railway.md): A step-by-step guide to
  install Saveroom on Railway.
* [Install on Ubuntu](installation/install-on-ubuntu.md): Instructions on how to install
  Docker and use it to install Saveroom on a fresh ubuntu install.
* [Third party hosting providers](installation/third-party-hosting-providers.md): A list
  of hosting/deployment providers that allow to easily self-host Saveroom.
* [Install with Helm](installation/install-with-helm.md): The recommended Kubernetes
  path. Deploys the split backend/web-frontend/Celery pods with optional bundled
  PostgreSQL/Redis and S3 media, and runs unmodified under OpenShift's restricted-v2 SCC.
* [Install on Amazon EKS](installation/install-on-eks.md): Saveroom on EKS behind an
  internal ALB fronted by CloudFront, with S3 media authenticated through IRSA.
* [Install with K8S](installation/install-with-k8s.md): An example performant 
  production ready K8S configuration for use as a starting point.
* [DEPRECATED: Install on Ubuntu](installation/old-install-on-ubuntu.md): A deprecated
  and now unsupported guide on how to manually install Saveroom and its required services
  on a fresh Ubuntu install. Please use the guides above instead.
* [Supported runtime dependencies and environments](installation/supported.md): Learn about
  the supported and recommended runtime dependencies.
* [Monitoring Saveroom](installation/monitoring.md): Learn how to monitor your Saveroom
  server using open telemetry.
* [Single sign-on with OpenID Connect](installation/sso-oidc.md): Full OIDC reference —
  provider keys, the user/staff/superuser profiles the IdP defines, a complete example and
  error codes.
* [Single sign-on with RHBK/Keycloak](installation/sso-rhbk-keycloak.md): Configure
  OpenID Connect login with Keycloak client roles deciding who may sign in and who is staff.
* [Managing workspace access](installation/workspace-access.md): Add existing users to
  workspaces, group them into teams, and set no access, viewer, editor or builder levels
  per database and table.
* [Data destinations, backups and datalake exports](installation/data-destinations.md):
  Ship backups to S3, Azure Blob Storage or a volume and restore them, and export table
  rows as Parquet to a datalake on a schedule.
* [Turning application types off instance-wide](installation/instance-settings.md): Use
  the admin settings to disable databases, the application builder, dashboards or
  automations for the whole instance.

## Saveroom Tutorials

* [Understanding Saveroom Formulas](tutorials/understanding-baserow-formulas.md): A
  tutorial explaining how to use the formula field in Saveroom.
* [Debugging Connection Issues](tutorials/debugging-connection-issues.md): A guide
  to help you troubleshoot and resolve common connection issues in Saveroom.

## API Usage

Saveroom provides various APIs detailed below:

* [REST API](apis/rest-api.md): An introduction to the REST API and information about
  API resources.
* [WebSocket API](apis/web-socket-api.md): An introduction to the WebSockets API which
  is used to broadcast real time updates.

## Technical Overviews

* [Introduction](technical/introduction.md): An introduction to some important technical
  concepts in Saveroom.
* [Database plugin](technical/database-plugin.md) An introduction to the database plugin
  which is installed by default.
* [Formula Technical Guide](technical/formula-technical-guide.md): A more technical
  guide about formulas aimed at developers who want to understand and work with
  internals of Saveroom formulas.
* [Undo Redo Technical Guide](technical/undo-redo-guide.md): How Saveroom implements undo
  redo technically.
* [Permissions handling Guide](technical/permissions-guide.md): How Saveroom implements
  permission checking technically.

## Development

Everything related to contributing and developing for Saveroom.

* [Development environment](./development/development-environment.md): More detailed
  information on baserow's local development environment.
* [Running the Dev Environment Locally](development/running-the-dev-env-locally.md): A
  step-by-step guide to run Saveroom locally for development.
* [Running the Dev Environment with Docker](development/running-the-dev-env-with-docker.md): A
  step-by-step guide to run Saveroom with Docker for development.
* [Directory structure](./development/directory-structure.md): The structure of all the
  directories in the Saveroom repository explained.
* [Tools](./development/tools.md): The tools (flake8, pytest, eslint, etc) and how to
  use them.
* [Code quality](./development/code-quality.md): More information about the code style,
  quality, choices we made, and how we enforce them.
* [Debugging](./development/debugging.md): Debugging tools and how to use them.
* [Create a template](./development/create-a-template.md): Create a template that can be
  previewed and installed by others.
* [Justfile reference](./development/justfile.md): Complete reference for all `just` commands
  available for development.
* [IntelliJ setup](./development/intellij-setup.md): How to configure Intellij to work
  well with Saveroom for development purposes.
* [Feature flags](./development/feature-flags.md): How Saveroom uses basic feature flags for optionally
  enabling unfinished or unready features.
* [E2E Testing](./development/e2e-testing.md): How to run Saveroom's end-to-end tests 
  and when to add your own.
* [Metrics and Logs](./development/metrics-and-logs.md): How to work with metrics and logs
  to aid with monitoring Saveroom as a developer.
* [Backend Tests](development/running-tests.md): A guide on how to run python tests for the backend.

## Plugins

Everything related to custom plugin development.

* [Plugin basics](./plugins/introduction.md): An introduction into Saveroom plugins.
* [Create application](./plugins/application-type.md): Want to create an application
  type? Learn how to do that here.
* [Create database table view](./plugins/view-type.md): Display table data like a
  calendar, Kanban board or however you like by creating a view type.
* [Create database table view filter](./plugins/view-filter-type.md): Filter the rows of
  a view with custom conditions.
* [Create database table field](./plugins/field-type.md): You can store data in a custom
  format by creating a field type.
* [Creata a field converter](./plugins/field-converter.md): Converters alter a field and
  convert the related data for specific field changes.

## Other

* [External resources related to Saveroom](./other/external-resources.md): A list of
  external third party resources.
