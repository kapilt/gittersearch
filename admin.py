import boto3
import click
import os
import app
import pprint

GITTER_TOKEN = os.environ.get('GITTER_TOKEN')


assert GITTER_TOKEN, "Environment variable for GITTER_TOKEN required"
assert app.TABLE_GITTER, "Environment variable for TABLE_GITTER required"


@click.group()
def cli():
    """GitterSearch Admin"""


@cli.command(name='db-rooms')
def db_rooms():
    for r in app.Room.get_all():
        print(r)


@cli.command(name='list-rooms')
@click.option('-t', '--room-type', type=click.Choice(['onetoone', 'repo']))
@click.option('-n', '--name')
def list_rooms(room_type, name, verbose=True):

    results = []
    gitter = app.GitterClient(GITTER_TOKEN)
    for r in gitter.rooms():
        if room_type and r['githubType'].lower() != room_type:
            continue
        if name and r['name'].lower() != name:
            continue
        if verbose:
            pprint.pprint(r)
        results.append(r)
    return results


@cli.command(name='add-room')
@click.option('-n', '--name')
@click.pass_context
def add_room(ctx, name):

    result = ctx.invoke(list_rooms, name=name, verbose=False)
    assert result, "No Room Found"
    room = result.pop()
    r = app.Room(
        ResourceId=room['id'],
        Name=room['name'],
        Topic=room['topic'],
        Uri=room['url'],
        Type=room['githubType'],
        AvatarUrl=room['avatarUrl'],
        UserCount=room['userCount'],
        LastSeen=None,
        OneToOne=None,
        State='Importing',
        Tags=room['tags'] and ','.join(room['tags']) or None,
        Version=str(room['v'])
    )

    r.save()
    print(result)
    print("invoke ingesting")
    print(app.invoke_fetch(r))


if __name__ == '__main__':
    cli()
