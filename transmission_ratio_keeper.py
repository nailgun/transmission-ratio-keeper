#!/usr/bin/env python
import sys
import base64
import urllib2
import logging
import json
import os

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S',
    filename=os.path.abspath(__file__)+'.log',
    level=logging.INFO)
log = logging.getLogger(__name__)

RPC_URL = 'http://localhost/transmission/rpc'
RPC_USER = 'torrent'
RPC_PASSWORD = 'password'
TARGET_RATIO = 1.1

class TransmissionRpc(object):
    def __init__(self, url, user, password):
        self.url = url
        self.user = user
        self.password = password
        self.opener = urllib2.build_opener()
        self.opener.addheaders = [
            ('Authorization', 'Basic '+base64.b64encode('%s:%s' % (self.user, self.password))),
            ('Content-Type', 'json'),
        ]
        self.sid = None

    def call(self, method, arguments=None):
        request_dict = dict(method=method)
        if arguments is not None:
            request_dict['arguments'] = arguments
        data = json.dumps(request_dict)
        response = None
        while response is None:
            try:
                response = self.opener.open(self.url, data)
            except urllib2.HTTPError, e:
                if e.code == 409:
                    if self.sid is not None:
                        raise
                    self.sid = e.info().get('X-Transmission-Session-Id', None)
                    if self.sid is None:
                        raise
                    self.opener.addheaders += [
                        ('X-Transmission-Session-Id', self.sid),
                    ]
                else:
                    raise
        response_dict = json.load(response)
        if response_dict['result'] != 'success':
            raise Exception(response_dict)
        if len(response_dict.keys()) != 2:
            raise Exception(response_dict)
        return response_dict['arguments']

def main():
    log.info('========= STARTED =========')
    rpc = TransmissionRpc(RPC_URL, RPC_USER, RPC_PASSWORD)
    stats = rpc.call('session-stats')
    if stats['current-stats']['downloadedBytes'] != 0:
        session_ratio = float(stats['current-stats']['uploadedBytes']) / float(stats['current-stats']['downloadedBytes'])
    else:
        session_ratio = sys.maxint
    log.info('session: duration %d days, downloaded %d Gb, uploaded %d Gb, ratio %.3f',
        stats['current-stats']['secondsActive'] / 86400,
        stats['current-stats']['downloadedBytes'] / 1024 / 1024 / 1024,
        stats['current-stats']['uploadedBytes'] / 1024 / 1024 / 1024,
        session_ratio,
    )
    if stats['cumulative-stats']['downloadedBytes'] != 0:
        total_ratio = float(stats['cumulative-stats']['uploadedBytes']) / float(stats['cumulative-stats']['downloadedBytes'])
    else:
        total_ratio = sys.maxint
    log.info('total: %d days, downloaded %d Gb, uploaded %d Gb, ratio %.3f',
        stats['cumulative-stats']['secondsActive'] / 86400,
        stats['cumulative-stats']['downloadedBytes'] / 1024 / 1024 / 1024,
        stats['cumulative-stats']['uploadedBytes'] / 1024 / 1024 / 1024,
        total_ratio,
    )

    if total_ratio < TARGET_RATIO:
        log.info('total ratio is lesser than target ratio')
    else:
        log.info('total ratio hit target')
        log.info('removing completed torrents')

        torrents = rpc.call('torrent-get', dict(fields=['id', 'leftUntilDone']))['torrents']
        completed_ids = [t['id'] for t in torrents if t['leftUntilDone'] == 0]
        log.info('%d torrents total, %d completed' % (len(torrents), len(completed_ids)))
        if completed_ids:
            rpc.call('torrent-remove', dict(ids=completed_ids))
        log.info('%d torrents removed' % len(completed_ids))

    log.info('=========  DONE  ==========')

if __name__ == '__main__':
    main()
