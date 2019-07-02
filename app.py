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

    fetch_arn = get_fetch_arn()
    client = boto3.client('lambda')

    for r in Room.get_all():
        client.invoke_function(
            FunctionArn=fetch_arn, Event={'Room': r},
            InvokeType='Event')


@app.lambda_function()
def fetch(event, context):
    """Fetch and index
    """

    gitter = get_gitter()
    es = get_es()
    room = Room.get(event['RoomId'])
    last = room['LastSeen']

    while context.time_remaining_in_millis() > 30000:
        buf = []
        for m in gitter.messages(
                room['RoomId'], AfterId=room['LastSeen']):
            m['room'] = room['name']
            m['from'] = '%s %s' % (
                m['fromUser']['username'], m['fromUser']['displayName'])
            m['mentioned'] = ' '.join([
                m['screeName'] for m in m['mentioned']])

            buf.append({'Data': json.dumps(m)})
            if buf % 100 == 0:
                last = m['id']
                break

        firehose.put_batch_records(
            DeliveryStreamName=FIREHOSE_STREAM, Records=buf)

#        ops = [{'_index': ELASTICSEARCH_IDX,
#                '_op_type': 'index',
#                '_type': 'message',
#                '_id': m['id'],
#                'doc': m} for m in buf]
#        es.bulk(ops)
        room['LastSeen'] = last
        room.save()


def get_fetch_arn():
    identity = sts.get_caller_identity()
    arn = ("arn:aws:lambda:{region}:{account_id}:"
           "function:{app_name}-{stage}-fetch").format(
               region=os.environ['AWS_REGION'],
               account_id=identity['Account'],
               app_name=app.app_name,
               stage='dev')
    return arn


def get_gitter():
    token = ssm.get_parameter(Name=TOKEN_PARAMETER)['Paramater']['Value']
    return GitterClient(token)


def get_es():
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key, credentials.secret_key,
        region=os.environ['AWS_DEFAULT_REGION'],
        session_token=credentials.token)
    es = Elasticsearch(hosts=[{
        'host': ELASTICSEARCH_HOST, 'port': 443}])
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

    @classmethod
    def get_all(cls):
        result = cls.__dynamoclass_client__.scan(
            TableName=cls.__dynamoclass_params__['table_name'])
        for r in result.get('Items'):
            yield cls(**cls._to_dataclass(r))


class GitterClient(object):

    log = logging.getLogger('gitter')

    def __init__(self, token, endpoint='https://api.gitter.im/v1'):
        self.endpoint = endpoint
        self.token = token

    def rooms(self):
        for r in self._request('/rooms'):
            yield r

    def messages(self, room, sinceId=None, beforeId=None):
        params = {'limit': 1000}
        if sinceId:
            params['sinceId'] = sinceId

        for mset in self._request('/rooms/%s' % room['id'], **params):
            for m in mset:
                yield m

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





