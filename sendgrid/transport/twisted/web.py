try:
    import json
except ImportError:
    import simplejson as json
from twisted.internet import reactor, defer
import twisted.internet.defer
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory

from sendgrid.transport.twisted import producer
from sendgrid.transport import web
from sendgrid.exceptions import SGServiceException


class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)


class Client(Protocol):
    def __init__(self, on_finish):
        self.on_finish = on_finish
        self.buffer = ""


    def dataReceived(self, bytes):
        self.buffer += bytes


    def connectionLost(self, reason):
        try:
            output = json.loads(self.buffer)
            if output['message'] == 'error':
                return self.on_finish.errback(SGServiceException(output['errors']))

            return self.on_finish.callback(None)
        except Exception:
            return self.on_finish.errback()


class Http(web.BaseHttp):
    """
    Transport to send emails using http with twisted
    """
    def send(self, message):
        """
        Send message

        Args:
            message: Sendgrid Message object

        Returns:
            deferred
        """
        url = self.get_url()
        data = self.get_api_params(message)
        files = {}

        if message.attachments:
            for attach in message.attachments:
                try:
                    f = open(attach['file'], 'rb')
                    files[attach['name']] = attach['file']
                    f.close()
                except IOError:
                    data['files[' + attach['name'] + ']'] = attach['file']

        producer_deferred = defer.Deferred()
        my_producer = producer.MultiPartProducer(files, data, None, producer_deferred)

        headers = Headers()
        headers.addRawHeader("Content-Type", "multipart/form-data; boundary=%s" % my_producer.boundary)

        agent_params = (reactor,)
        if self.ssl:
            agent_params = (reactor, WebClientContextFactory())
        d = Agent(*agent_params).request('POST', url, headers, my_producer)
        d.addCallbacks(self._handle_response, self._handle_error)
        return d


    def _handle_response(self, response):
        on_finish = twisted.internet.defer.Deferred()
        response.deliverBody(Client(on_finish))
        return on_finish


    def _handle_error(self, reason):
        return reason


    def _request(self):
        pass