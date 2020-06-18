import click

from drillmaster import services

@click.group()
def cli():
    pass

@cli.command()
@click.option("--run-new-containers", default=False,
              help="Create new containers instead of using existing")
@click.option("--exclude", help="Names of services to exclude (comma-separated)")
@click.option("--network-name", default="drillmaster-network", help="Network to use")
@click.option("--timeout", type=int, default=300, help="Timeout for starting a service (seconds)")
def start(run_new_containers, exclude, network_name, timeout):
    services.start_services(run_new_containers, exclude, network_name, timeout)


@cli.command()
@click.option("--exclude", help="Names of services to exclude (comma-separated)")
@click.option("--network-name", default="drillmaster-network", help="Network to use")
@click.option("--remove", is_flag=True, default=False, help="Remove container images and network")
@click.option("--timeout", type=int, default=50, help="Timeout for stopping a service (seconds)")
def stop(exclude, network_name, remove, timeout):
    exclude = exclude or []
    services.stop_services(exclude, network_name, remove, timeout)
