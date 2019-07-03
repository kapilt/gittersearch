from dataclasses import asdict
import json
import logging
import os
import time
from urllib.parse import urlencode
import requests

import boto3
from chalice import Chalice
from dynamoclasses import dynamoclass
from elasticsearch import Elasticsearch
from requests_aws4auth import AWS4Auth

TOKEN_PARAMETER = os.environ.get('GITTER_TOKEN_PARAM')
TABLE_GITTER = os.environ.get('TABLE_GITTER')
ELASTICSEARCH_IDX = os.environ.get('ELASTICSEARCH_INDEX', 'gitter')
ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST')
FIREHOSE_STREAM = os.environ.get('FIREHOSE_STREAM')

app = Chalice('gitter_search')
ssm = boto3.client('ssm')
sts = boto3.client('sts')
firehose = boto3.client('firehose')

MessageMapping = {
    'id': 'keyword',
    'text': 'text',
    'from': 'text',
    'mentioned': 'text',
    'issues': 'array',
    'sent': {
        'type': 'date',
        'format': 'strict_date_optional_time',
    }
}


@app.route('/')
def index():
    return {'hello': 'world'}


@app.route('/search')
def search():
    es = get_es()


###

@app.schedule('rate(1 hour)')
def fanned_fetch(event):
    print('fetch rooms')
    for r in Room.get_all():
        if r.State != 'Imported':
            continue
        result = invoke_fetch(r)
        print(r)


@app.lambda_function()
def fetch(event, context):
    """Fetch and index
    """
    gitter = get_gitter()
    room = Room.get(partition_key=event['Room']['ResourceId'], sort_key=None)
    lastSeen = room.LastSeen != 'True' and room.LastSeen or None
    direction = (
        room.State == 'Importing' and MessageIterator.Backward
        or MessageIterator.Forward)

    print("Get Room:%s State:%s Last:%s" % (room.Name, room.State, lastSeen))
    message_iterator = MessageIterator(
        gitter, room.ResourceId, direction, lastSeen)

    while context.get_remaining_time_in_millis() > 30000:
        buf = []
        for m in message_iterator:
            m['room'] = room.Name
            m['from'] = '%s %s' % (
                m['fromUser']['username'], m['fromUser']['displayName'])
            m['mentioned'] = ' '.join([
                m['screeName'] for m in m['mentions']])
            buf.append({'Data': json.dumps(m)})
            if buf % 100 == 0:
                break
        if not buf:
            break
        firehose.put_batch_records(
            DeliveryStreamName=FIREHOSE_STREAM, Records=buf)
        print("message batch %s" % buf[-1])
        room.LastSeen = buf[message_iterator.dir_index]
        room.save()
        break

    if buf:
        room.State = 'Importing'
        room.save()
        invoke_fetch(room)

    else:
        room.State = 'Ingested'
        room.save()


def invoke_fetch(room):
    fetch_arn = get_fetch_arn()
    client = boto3.client('lambda')
    return client.invoke(
        FunctionName=fetch_arn,
        Payload=json.dumps({'Room': asdict(room)}),
        InvocationType='Event')


def get_fetch_arn():
    identity = sts.get_caller_identity()
    arn = ("arn:aws:lambda:{region}:{account_id}:"
           "function:{app_name}-{stage}-fetch").format(
               region=os.environ['AWS_REGION'],
               account_id=identity['Account'],
               app_name=app.app_name.replace('_', ''),
               stage='dev')
    return arn


def get_gitter():
    token = ssm.get_parameter(Name=TOKEN_PARAMETER)['Parameter']['Value']
    return GitterClient(token)


def get_es():
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key, credentials.secret_key,
        service='es',
        region=os.environ['AWS_DEFAULT_REGION'],
        session_token=credentials.token)
    es = Elasticsearch(hosts=[{
        'host': ELASTICSEARCH_HOST, 'port': 443}], http_auth=auth)
    return es


@dynamoclass(table_name=TABLE_GITTER, partition_key_name='ResourceId')
class Room:

    ResourceId: str
    LastSeen: str
    Name: str
    Topic: str
    UserCount: int
    Type: str
    Tags: str
    Version: str
    OneToOne: str
    Uri: str
    AvatarUrl: str
    State: str

    @classmethod
    def get_all(cls):
        result = cls.__dynamoclass_client__.scan(
            TableName=cls.__dynamoclass_params__['table_name'])
        for r in result.get('Items'):
            yield cls(**cls._to_dataclass(r))


class MessageIterator(object):

    Forward = (-1, 'afterId')
    Backward = (0, 'beforeId')

    def __init__(self, client, room_id, direction, lastSeen=None):
        self.client = client
        self.params = {'roomId': room_id, 'limit': 100}
        assert (direction == self.Forward
                or direction == self.Backward), "Unknown direction" % direction
        self.dir_index, self.dir_key = direction
        if lastSeen:
            self.params[self.dir_key] = lastSeen
        self._buf = None

    def __iter__(self):
        while True:
            if not self._buf:
                self._buf = self.client.messages(**self.params)
            for m in self._buf:
                yield m
            if not self._buf:
                break
            self.params[self.dir_key] = self._buf[self.dir_index]['id']
            self._buf = None


class GitterClient(object):

    log = logging.getLogger('gitter')

    def __init__(self, token, endpoint='https://api.gitter.im/v1'):
        self.endpoint = endpoint
        self.token = token

    def rooms(self):
        return self._request('/rooms')

    def messages(self, roomId, afterId=None, beforeId=None, limit=100):
        params = {'limit': limit}
        if afterId and afterId != 'True':
            params['afterId'] = afterId
        elif beforeId:
            params['beforeId'] = beforeId
        return self._request('/rooms/%s/chatMessages' % roomId, **params)

    def _request(self, path, **params):
        qs = urlencode(params)
        uri = self.endpoint + path
        if qs:
            uri += '?%s' % qs
        r = requests.get(
            uri, headers={'Authorization': 'Bearer %s' % self.token})
        r.raise_for_status()
        remaining = int(r.headers.get('X-RateLimit-Remaining', 1000))
        if remaining < 10:
            self.log.info('slowing down... remaining:%d', remaining)
            time.sleep(10)
        else:
            time.sleep(1)
        return r.json()



#                '_op_type': 'index',
#                '_type': 'message',
#                '_id': m['id'],
#                'doc': m} for m in buf]
#        es.bulk(ops)
