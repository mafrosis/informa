import re
import socket
from urllib.parse import urlparse
from socket import error as SocketError
import xmlrpc.client


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

    def get_torrents(self, tag=None):
        try:
            torrents = self.server.d.multicall(
                'main', 'd.complete=', 'd.size_bytes=', 'd.completed_bytes=', 'd.get_name=', 'd.get_custom1='
            )
            if torrents is None:
                return None

            data = []
            for t in torrents:
                if not tag or (tag and t[4] == tag):
                    # calculate % done
                    data.append({
                        'name': t[3],
                        'done': '{0:.1f}%'.format(float(t[2]) / float(t[1]) * 100),
                    })
                    if tag:
                        data['tag'] = t[4]

            return data

        except (xmlrpc.client.Fault, SocketError) as e:
            # TODO error logging etc
            return None
