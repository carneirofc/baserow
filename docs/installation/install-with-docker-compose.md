# Install with Docker compose

> Any questions, problems or suggestions with this guide? Ask a question in our
> [issue tracker](https://github.com/carneirofc/baserow/issues) or contribute the change yourself at
> https://github.com/carneirofc/baserow/tree/develop/docs .

## Quickstart

The following config is the easiest way of deploying Saveroom with docker-compose and
just uses the all-in-one image and a single container. If you use this config then you
should instead refer to the [Install with Docker](./install-with-docker.md)
guide on the specifics of how to work with this image.

```yaml
services:
  baserow:
    container_name: baserow
    image: ghcr.io/carneirofc/baserow:latest
    environment:
      BASEROW_PUBLIC_URL: 'http://localhost'
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - baserow_data:/baserow/data
volumes:
  baserow_data:
```

The rest of this guide will instead deal with the default `docker-compose.yml`
found in the root of our git repository which runs each Saveroom service as a separate
container.

## Installing requirements

If you haven't already installed docker and docker-compose on your computer you can do
so by following the instructions on https://docs.docker.com/desktop/ and
https://docs.docker.com/compose/install/.

> Docker-compose version 1.19.0 and Docker version 19.03 are the minimum versions
> required by our provided files.

## Downloading the Saveroom example docker-compose.yml

You can download the example Saveroom `docker-compose.yml` by either directly downloading
the file from
[https://github.com/carneirofc/baserow/blob/master/docker-compose.yml](https://github.com/carneirofc/baserow/blob/master/docker-compose.yml)
and running:

```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/carneirofc/baserow/refs/heads/develop/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/carneirofc/baserow/refs/heads/develop/.env.example 
curl -o Caddyfile https://raw.githubusercontent.com/carneirofc/baserow/refs/heads/develop/Caddyfile
# Edit .env and set your own secure passwords for the 3 required variables at the top. 
gedit .env
docker-compose up -d
```

or by directly cloning our git repo so you can get updates easier:

```bash
git clone --depth=1 --branch develop https://github.com/carneirofc/baserow.git ~/saveroom
cd ~/saveroom
cp .env.example .env
# Edit .env and set your own secure passwords for the 3 required variables at the top. 
gedit .env
docker-compose up -d
# To update to the latest run:
docker-compose down
git pull
docker-compose up -d
```

> There is a security flaw with docker and the ufw firewall.
> By default docker when exposing ports on 0.0.0.0 will bypass any ufw firewall rules
> and expose the above container publicly from your machine on its network. If this
> is not intended then please set HOST_PUBLISH_IP to 127.0.0.1 so Saveroom can only be
> accessed from the machine it is running on.
> Please see https://github.com/chaifeng/ufw-docker for more information and how to
> setup ufw to work securely with docker.

## Usage

To use this docker-compose.yml to run Saveroom you must set the three  
environment variables `SECRET_KEY`, `DATABASE_PASSWORD` and `REDIS_PASSWORD`. See the
section below for more details. If you receive the following error it is because you
need to set the required environment variables first:

```
ERROR: Missing mandatory value for "environment" option interpolating
```

If you are upgrading from Baserow 1.8.2 or earlier please read the additional section
below.

See [Configuring Saveroom](configuration.md) for information on the other environment
variables you can configure.

## How to set environment variables

You can set these variables by using docker-compose env file
(https://docs.docker.com/compose/environment-variables/#the-env-file):

1. Copy the `.env.example` file found in the root of Baserows repository
   (https://github.com/carneirofc/baserow/blob/master/.env.example)  to `.env`:

```
curl -o .env https://raw.githubusercontent.com/carneirofc/baserow/refs/heads/develop/.env.example
```

2. Edit `.env` and provide values for the missing environment variables.
3. `docker-compose up`

Alternatively you can set these variables by either running docker-compose with the
environment variables set on the command line (fill in secure values first):

```
SECRET_KEY= DATABASE_PASSWORD= REDIS_PASSWORD= docker-compose up
```

## Upgrading

1. It is recommended that you backup your data before upgrading, see the Backup sections
   below for more details on how to do this.
2. Stop your existing Saveroom install when safe to do so:
   `docker-compose down`
3. Get the latest Saveroom version by running:
   `git pull`
4. Startup the new version of Saveroom by running: `docker-compose up -d`
5. Monitor the logs using: `docker-compose logs -f`
6. Once you see the following log line your Saveroom upgraded and is now available again:

```
[BASEROW-WATCHER][2022-05-10 08:44:46] Saveroom is now available at ...
```

## How To

### Running management commands

You can see and run the Saveroom backend management commands like so:

```bash
docker-compose exec backend /baserow/backend/docker/docker-entrypoint.sh help
```

### View the logs

```bash
$ docker-compose logs 
```

### Run Saveroom alongside existing services

Saveroom's docker-compose files will automatically expose the `caddy` service on your
network on ports 80 and 433 by default. If you already have applications or services
using those ports the Saveroom service which uses that port will crash. To fix this you
can set the `WEB_FRONTEND_PORT` variable to change the default of port 80 and
`WEB_FRONTEND_SSL_PORT` to change the default port of 443.

```bash
$ WEB_FRONTEND_SSL_PORT=444 WEB_FRONTEND_PORT=3000 docker-compose up 
```

### Using a Domain with automatic https

If you have a domain name and have correctly configured DNS then you can run the
following command to make Saveroom available at the domain with
[automatic https](https://caddyserver.com/docs/automatic-https#overview) provided by
Caddy.

> Append `,http://localhost` to BASEROW_CADDY_ADDRESSES if you still want to be able to
> access your server from the machine it is running on using http://localhost. See
> [Caddy's Address Docs](https://caddyserver.com/docs/caddyfile/concepts#addresses)
> for all supported values for BASEROW_CADDY_ADDRESSES.

```bash
BASEROW_PUBLIC_URL=https://www.REPLACE_WITH_YOUR_DOMAIN.com \
BASEROW_CADDY_ADDRESSES=:443 \
docker-compose up
```

### Behind a reverse proxy already handling ssl

```bash
WEB_FRONTEND_SSL_PORT= \
BASEROW_PUBLIC_URL=https://www.REPLACE_WITH_YOUR_DOMAIN.com \
docker-compose up
```

### On a nonstandard HTTP port

```bash
WEB_FRONTEND_PORT=3000 \
BASEROW_PUBLIC_URL=https://www.REPLACE_WITH_YOUR_DOMAIN.com:3000 \
docker-compose up
```

### Disable automatic migration

You can disable automatic migration by setting the `MIGRATE_ON_STARTUP` environment
variable to `false` (or any value which is not `true`) like so:

```bash
MIGRATE_ON_STARTUP=false docker-compose up -d
```

### Run a one off migration

```bash
# Use run if you have stopped your docker-compose environment
docker-compose run backend manage migrate
# Use exec otherwise
docker-compose exec backend /baserow/backend/docker/docker-entrypoint.sh manage migrate
```

### Disable automatic template syncing

You can disable automatic baserow template syncing by setting the
`BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION` environment variable to `false` (or any
value which is not `true`) like so:

```bash
BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION=false docker-compose up -d
```

### Back-up your Saveroom DB

1. Please read the output of `docker-compose run backend manage backup_baserow --help`.
2. Please ensure you only back-up a Saveroom database which is not actively being used by
   a running Saveroom instance or any other process which is making changes to the
   database.

```bash
mkdir ~/baserow_backups
# The folder must be the same UID:GID as the user running inside the container, which
# for the local env is 9999:9999, for the dev env it is your own UID:GID
# when using `just dc-dev`
sudo chown 9999:9999 ~/baserow_backups/ 
docker-compose run -v ~/baserow_backups:/baserow/backups backend backup -f /baserow/backups/baserow_backup.tar.gz 
# backups/ now contains your Saveroom backup.
```

### Restore your Saveroom DB from a back-up

1. Please read the output of `docker-compose run backend manage restore_baserow --help`
1. Please ensure you never restore Saveroom using a pooled connection but instead do the
   restoration via direct database connection.
1. Make a new, empty database to restore the back-up file into, please do not overwrite
   existing databases as this might cause database inconsistency errors.

```bash
docker-compose run -v ~/baserow_backups:/baserow/backups backend restore -f /baserow/backups/baserow_backup.tar.gz 
```
