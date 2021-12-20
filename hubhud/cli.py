import click
import logging

from sqlalchemy.orm import Session

from .github import sync as github_sync
from .gitter import sync as gitter_sync
from .schema import get_db

log = logging.getLogger("hubhud")


@click.group()
def cli():
    """HubHud - Tracking Github"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s: %(name)s:%(levelname)s %(message)s"
    )


@cli.group()
def sync():
    """Sync information sources to local database"""


@sync.command()
@click.option("-f", "--db", envvar="HUD_DB", required=True)
@click.option("-p", "--project", envvar="HUB_PROJECT", required=True)
def gitter(db, project):
    log.info("syncing gitter messages for %s", project)
    engine = get_db(db)
    with Session(engine) as s:
        count = gitter_sync(s, project)
    log.info("finished - added %d messages for %s", count, project)


@sync.command()
@click.option("-f", "--db", envvar="HUD_DB", required=True)
@click.option("-p", "--project", envvar="HUB_PROJECT", required=True)
@click.option("--rename")
def github(db, project, rename):
    """Sync github events for a project into the db"""
    log.info("syncing github events for %s", project)
    engine = get_db(db)
    with Session(engine) as s:
        count = github_sync(s, project, rename)

    log.info("finished - added %d events for %s", count, project)


if __name__ == "__main__":
    try:
        cli()
    except Exception:
        import pdb, traceback, sys

        traceback.print_exc()
        pdb.post_mortem(sys.exc_info()[-1])
