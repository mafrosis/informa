import math
import re
import socket
from urllib.parse import urlparse
from socket import error as SocketError
import xmlrpc.client


class RtorrentError(Exception):
    pass


class SCGITransport(xmlrpc.client.Transport):
    def single_request(self, host, handler, request_body, verbose=0):
        # create SCGI header
        header = 'CONTENT_LENGTH\x00{}\x00SCGI\x001\x00'.format(len(request_body))
        request_body = '{}:{},{}'.format(len(header), header, request_body)
        sock = None

        try:
            if host:
                host, port = host.split(':')
                addrinfo = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                sock = socket.socket(*addrinfo[0][:3])
                sock.connect(addrinfo[0][4])
            else:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(handler)

            sock.send(request_body.encode('ascii'))
            return self.parse_response(sock.makefile())

        finally:
            if sock:
                sock.close()

    def parse_response(self, response):
        p, u = self.getparser()

        response_body = ''
        while True:
            data = response.read(1024)
            if not data:
                break
            response_body += data

        try:
            # Remove SCGI headers from the response.
            response_header, response_body = re.split(r'\n\s*?\n', response_body, maxsplit=1)
            p.feed(response_body)
            p.close()
            return u.close()

        except ValueError:
            # TODO log?
            pass


class SCGIServerProxy(xmlrpc.client.ServerProxy):
    def __init__(self, uri, transport=None, encoding=None, allow_none=False):
        uri = urlparse(uri)
        if uri.scheme != 'scgi':
            raise IOError('unsupported XML-RPC protocol')

        self.__host = uri.netloc
        self.__handler = uri.path

        if transport is None:
            transport = SCGITransport()
            self.__transport = transport

        self.__encoding = encoding
        self.__allow_none = allow_none

    def __close(self):
        self.__transport.close()

    def __request(self, methodname, params):
        request = xmlrpc.client.dumps(
            params,
            methodname,
            encoding=self.__encoding,
            allow_none=self.__allow_none
        )

        response = self.__transport.request(
            self.__host,
            self.__handler,
            request,
        )

        if not response:
            return None
        elif len(response) == 1:
            response = response[0]

        return response

    def __repr__(self):
        return (
            "<SCGIServerProxy for %s%s>" % (self.__host, self.__handler)
        )

    __str__ = __repr__

    def __getattr__(self, name):
        # magic method dispatcher
        return xmlrpc.client._Method(self.__request, name)

    def __call__(self, attr):
        """
        A workaround to get special attributes on the ServerProxy
        without interfering with the magic __getattr__
        """
        if attr == "close":
            return self.__close
        elif attr == "transport":
            return self.__transport

        raise AttributeError("Attribute %r not found" % (attr,))


class RTorrent():
    def __init__(self, host, port):
        self.server = SCGIServerProxy('scgi://{}:{}/'.format(host, port))

    def get_torrents(self, tag_filter=None):
        try:
            downloads = self.server.d.multicall(
                'main',
                'd.hash=',
                'd.name=',
                'd.completed_bytes=',
                'd.custom1='
            )
            if downloads is None:
                raise RtorrentError('Failed to load from rtorrent SCGI')

        except ConnectionRefusedError:
            raise RtorrentError('Rtorrent is down')
        except (xmlrpc.client.Fault, SocketError) as e:
            raise RtorrentError('Failed to load from rtorrent SCGI: {}'.format(e))

        data = {}

        for d in downloads:
            if not tag_filter or (tag_filter and d[4] == tag_filter):
                # calculate % done
                data[d[0]] = {
                    'name': d[1],
                    'size': format_size(d[2]),
                    'tag': d[3],
                    'files': [],
                }

                try:
                    files = self.server.f.multicall(
                        d[0],
                        '',
                        'f.path=',
                        'f.size_bytes=',
                        'f.size_chunks=',
                        'f.completed_chunks=',
                        'f.priority=',
                    )
                except ConnectionRefusedError:
                    raise RtorrentError('Rtorrent is down')
                except (xmlrpc.client.Fault, SocketError) as e:
                    raise RtorrentError('Failed to load d.files from rtorrent SCGI: {}'.format(e))

                for f in files:
                    data[d[0]]['files'].append({
                        'filename': f[0],
                        'size': format_size(f[1]),
                        'progress': '{0:.1f}%'.format(float(f[3]) / float(f[2]) * 100),
                        'priority': 'skip' if f[4] == 0 else 'high' if f[4] == 2 else 'normal',
                    })

                try:
                    # torrent total progress based on each file's progress, ignoring "skipped" files
                    torrent_progress = sum([f[3] for f in files if f[4] > 0]) / sum([f[2] for f in files if f[4] > 0]) * 100
                except ZeroDivisionError:
                    # all files are "skip"
                    torrent_progress = 0

                data[d[0]]['progress'] = '{0:.1f}%'.format(torrent_progress)
                data[d[0]]['complete'] = torrent_progress == 100

        return data


    def set_tag(self, hash_id, tag_name):
        '''
        Set tag in custom1 field on a torrent

        Params:
            hash_id (str):      download hash_id
            tag_name (str):     tag text
        '''
        try:
            self.server.d.custom1.set(hash_id, tag_name)

        except ConnectionRefusedError:
            raise RtorrentError('Rtorrent is down')
        except (xmlrpc.client.Fault, SocketError) as e:
            raise RtorrentError('Failed to load from rtorrent SCGI: {}'.format(e))


    def set_file_priority(self, hash_id, file_index, priority):
        '''
        Set priority of a file in a torrent

        Params:
            hash_id (str):      download hash_id
            file_index (int):   position in download.files[] from get_torrents()
            priority (int):     0: skip, 1: normal, 2: high
        '''
        try:
            self.server.f.priority.set('{}:f{}'.format(hash_id, file_index), priority)

        except ConnectionRefusedError:
            raise RtorrentError('Rtorrent is down')
        except (xmlrpc.client.Fault, SocketError) as e:
            raise RtorrentError('Failed to load from rtorrent SCGI: {}'.format(e))


def format_size(size):
    if size <= 0:
        return '0B'

    i = int(math.floor(math.log(size, 1024)))
    s = round(size / math.pow(1024, i), 2)

    return '{}{}'.format(s, ('B', 'KB', 'MB', 'GB', 'TB', 'PB')[i])
