from django.test import TestCase
from .models import BridgeAccount, BridgeThread, BridgeMessage

class BridgeSmokeTest(TestCase):
    def test_create_message_and_thread(self):
        a = BridgeAccount.objects.create(user_id='00000000-0000-0000-0000-000000000000', external_app='TEST', external_user_id='ext-1', access_token='tok')
        t = BridgeThread.objects.create(external_app='TEST', external_thread_id='thread-1')
        m = BridgeMessage.objects.create(bridge_thread=t, direction='INBOUND', message_type='TEXT', payload={'text':'hi'})
        self.assertEqual(t.messages.count(), 1)