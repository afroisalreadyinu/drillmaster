[![afroisalreadyinu](https://circleci.com/gh/afroisalreadyinu/drillmaster.svg?style=svg)](https://app.circleci.com/pipelines/github/afroisalreadyinu/drillmaster)

# drillmaster

drillmaster is a Python application that can be used to locally start multiple
dependent docker services, individually rebuild and restart them, and run
initialization jobs. The definitions for services can be written in Python,
allowing you to use

## Why not docker-compose?

First and foremost, this is not YAML. `docker-compose` is in the school of
yaml-as-service-description, which means that going beyond a static description
of a service set necessitates templates, or some kind of scripting. One could as
well use a full-blown programming language, while trying to keep simple things
simple. Another thing sorely missing in `docker-compose` is lifecycle hooks,
i.e. a mechanism whereby scripts can be executed when the state of a container
changes. Lifecycle hooks have been
[requested](https://github.com/docker/compose/issues/1809)
[multiple](https://github.com/docker/compose/issues/5764)
[times](https://github.com/compose-spec/compose-spec/issues/84), but were not
deemed to be in the domain of `docker-compose`.

The intention is to develop this package to a full-blown distributed testing
framework, which will probably take some time.

## Usage

Here is a very simple service specification:

```python
#! /usr/bin/env python3
import drillmaster

class Database(drillmaster.Service):
    name = "appdb"
    image = "postgres:10.6"
    env = {"POSTGRES_PASSWORD": "dbpwd",
           "POSTGRES_USER": "dbuser",
           "POSTGRES_DB": "appdb" }
    ports = {5432: 5433}

class Application(drillmaster.Service):
    name = "python-todo"
    image = "afroisalreadyin/python-todo:0.0.1"
    env = {"DB_URI": "postgresql://dbuser:dbpwd@appdb:5432/appdb"}
    dependencies = ["appdb"]
    ports = {8080: 8080}
    stop_signal = "SIGINT"

if __name__ == "__main__":
    drillmaster.cli()
```

A **service** is defined by subclassing `drillmaster.Service` and overriding, in
the minimal case, the fields `image` and `name`. The `env` field specifies the
enviornment variables; as in the case of the `appdb` service, you can use
ordinary variables in this and any other value. The other available fields will
be explained later. Here, we are creating two services: The application service
`python-todo` (a simple Flask todo application defined in the `sample-apps`
directory) depends on `appdb` (a Postgresql container), specified through the
`dependencies` field. As in `docker-compose`, this means that `python-todo` will
get started after `appdb` reaches running status.

The `drillmaster.cli` function is the main entry point; you need to execute it
in the main routine of your scirpt. Let's run this script without arguments,
which leads to the following output:

```
Usage: drillmaster-main.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  start
  stop
```

We can start our small ensemble of services by running `./drillmaster-main.py
start`. After spitting out some logging text, you will see that starting the
containers failed, with the `python-todo` service throwing an error that it
cannot reach the database. The reason for this error is that the Postgresql
process has started, but is still initializing, and does not accept connections
yet. The standard way of dealing with this issue is to include backoff code in
your application that checks on the database port regularly, until the
connection is accepted. `drillmaster` offers an alternative with [lifecycle
events](#lifecycle-events). For the time being, you can simply rerun
`./drillmaster-main.py start`, which will restart only the `python-todo`
service, as the other one is already running. You should be able to navigate to
`http://localhost:8080` and view the todo app page.

You can also exclude services from the list of services to be started with the
`--exclude` argument; `./drillmaster-main.py start --exclude python-todo` will
start only `appdb`. If you exclude a service that is depended on by another, you
will get an error.

### Stopping services

Once you are done working, you can stop the running services with
`drillmaster-main.py stop`. This will stop the services in the reverse order of
dependency, i.e. first `python-todo` and then `appdb`. Exclusion is possible
also when stopping services with the same `--exclude` argument. Running
`./drillmaster-main.py stop --exclude appdb` will stop only the `python-todo`
service. If you exclude a service whose dependency will be stopped, you will get
an error.

## Lifecycle events

A service has two methods that can be overriden: `ping` and `post_start_init`.
Both of these by default do nothing; when implemented, they are executed one
after the other, and the service is not registered as `running` before each
succeed. The `ping` method is executed repeatedly, with 0.1 seconds gap, for
`timeout` seconds, until it returns True. Once `ping` returns, `post_start_init`
is called.

## Ports and hosts

TBW

### The global context

TBW

## Service fields

- **name**: The name of the service. Must be unique. The container can be
    contacted on the network under this name; must therefore be a valid
    hostname.

- **image**: Container image of the service.

- **env**: Environment variables to be injected into the service container, as a
    dict. The values of this dict can contain extrapolations from the global
    context; these extrapolations are executed when the service starts.

- **dependencies**: A list of the dependencies of a service by name. If there
    are any invalid or circular dependencies, an error will be raised.

## Todos

- [ ] Don't use existing container if env changed
- [ ] Stop signal as an option on service def