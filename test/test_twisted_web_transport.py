from twisted.trial import unittest
from twisted.internet import defer
import fudge
from fudge.inspector import arg
import sendgrid
from sendgrid.transport.twisted import web


class TestTwistedTransports(unittest.TestCase):
    def test_twisted_web_transport_sending(self):
        transport = web.Http('username', 'password', ssl=False)
        message = sendgrid.Message("example@example.com", "subject1", "plain_text", "html")
        message.add_to("recipient@example.com")

        d_response = defer.Deferred()

        request = fudge.patch_object("twisted.web.client.Agent", "request", fudge.Fake('Agent.request')\
            .expects_call().with_args('POST', 'http://sendgrid.com/api/mail.send.json', arg.any(), arg.any())\
            .returns(d_response)
        )

        result = transport.send(message)
        d_response.callback(fudge.Fake('response').expects("deliverBody"))

        result.result.callback("success")
        self.assertEqual(result.result, "success", "Test request")

        request.restore()


    def test_twisted_web_transport_protocol(self):
        # try with invalid server answer
        on_finish = fudge.Fake('on_finish').expects("errback")
        c = web.Client(on_finish)
        c.dataReceived("1")
        self.assertEqual(c.buffer, "1")
        c.dataReceived("2")
        self.assertEqual(c.buffer, "12")
        c.connectionLost("SHOULD FAIL")

        # try error response
        on_finish = fudge.Fake('on_finish').expects("errback").with_args(arg.passes_test(lambda x: str(x) == "Bad username / password"))
        c = web.Client(on_finish)
        c.dataReceived('{"message": "error", "errors": "Bad username / password"}')
        c.connectionLost("SHOULD FAIL")

        # try success response
        on_finish = fudge.Fake('on_finish').expects("callback").with_args(None)
        c = web.Client(on_finish)
        c.dataReceived('{"message": "success", "success": "ok"}')
        c.connectionLost("SHOULD SUCCEED")