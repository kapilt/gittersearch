import click
import logging

import sqlalchemy as rdb
from sqlalchemy.orm import Session

from .github import GithubEvent, get_events as get_hub_events
from .gitter import Message, get_messages
from .schema import get_db

log = logging.getLogger('hubhud')


@click.group()
def cli():
    """HubHud - Tracking Github"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s: %(name)s:%(levelname)s %(message)s")


@cli.group()
def sync():
    """Sync information sources to local database"""


@sync.command()
@click.option("-f", "--db", envvar="HUD_DB", required=True)
@click.option("-p", "--project", envvar="HUB_PROJECT", required=True)
def gitter(db, project):
    log.info('syncing gitter messages for %s', project)
    engine = get_db(db)
    with Session(engine) as s:
        last = s.query(Message).order_by(rdb.desc(Message.sent)).limit(1).one_or_none()
        params = {}
        if last:
            params['since'] = last.id
        count = 0
        for e in get_messages(project, **params):
            s.add(e)
            count += 1
            if count % 1000 == 0:
                log.info('added %d events for %s', count, project)
        s.commit()
    log.info('finished - added %d events for %s', count, project)
    

@sync.command()
@click.option("-f", "--db", envvar="HUD_DB", required=True)
@click.option("-p", "--project", envvar="HUB_PROJECT", required=True)
@click.option("--rename")
def github(db, project, rename):
    """Sync github events for a project into the db"""
    log.info('syncing github events for %s', project)
    engine = get_db(db)
    with Session(engine) as s:
        last = s.query(GithubEvent).order_by(rdb.desc(GithubEvent.created_at)).limit(1).one_or_none()
        params = {}
        if last:
            params['start'] = last.created_at
        count = 0
        for e in get_hub_events(project, **params):
            if rename:
                e.repo_name = rename
            s.add(e)
            count += 1
            if count % 1000 == 0:
                log.info('added %d events for %s', count, project)
        s.commit()
    log.info('finished - added %d events for %s', count, project)        



if __name__ == '__main__':
    try:
        cli()
    except Exception:
        import pdb, traceback, sys
        traceback.print_exc()
        pdb.post_mortem(sys.exc_info()[-1])
    

    
