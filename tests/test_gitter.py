import os
import pytest

from dateutil.parser import parse
from hubhud.gitter import GitterClient, Room, MessageIterator, Message



@pytest.mark.skipif(not os.environ.get('GITTER_TOKEN'), reason='api token required')
def test_get_rooms():
    client = GitterClient(os.environ['GITTER_TOKEN'])
    rooms = [r for r in client.rooms() if r.githubType != 'ONETOONE']
    rnames = {r.url for r in rooms}
    assert '/cloud-custodian/cloud-custodian' in rnames
    

@pytest.mark.skipif(not os.environ.get('GITTER_TOKEN'), reason='api token required')
def test_get_messages():
    client = GitterClient(os.environ['GITTER_TOKEN'])
    messages = client.messages('5717b4ae659847a7aff3b704', limit=10)
    assert len(messages) == 10


@pytest.mark.skipif(not os.environ.get('GITTER_TOKEN'), reason='api token required')
def test_message_iterator():
    client = GitterClient(os.environ['GITTER_TOKEN'])
    room = client.get_room('cloud-custodian/cloud-custodian')
    message_iter = MessageIterator(client, room)
    message_iter.params['limit'] = 10
    messages = []
    
    for m in message_iter:
        messages.append(m)
        if len(messages) == 20:
            break

    assert len(messages) == 20
    assert parse(messages[0].sent) > parse(messages[-1].sent)


            


    
