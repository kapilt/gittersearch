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
        Tags=','.join(room['tags']),
        Version=str(room['v'])
    )
    try:
        r.save()
    except:
        import pdb, sys, traceback
        traceback.print_exc()
        pdb.post_mortem(sys.exc_info()[-1])
    print(result)


if __name__ == '__main__':
    cli()
