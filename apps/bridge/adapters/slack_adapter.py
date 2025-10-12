from slack_sdk import WebClient

class SlackAdapter:
    def __init__(self, token):
        self.client = WebClient(token=token)

    def send_message(self, channel, text, attachments=None):
        resp = self.client.chat_postMessage(channel=channel, text=text, attachments=attachments)
        return resp.data

    def fetch_thread(self, channel, ts):
        # use conversations.replies
        pass