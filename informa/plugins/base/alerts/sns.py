import logging

import boto.sns

logger = logging.getLogger('informa')


class SNSAlert:
    @staticmethod
    def prepare(access_id, secret_key, topic):
        alert = SNSAlert()
        alert.conn = boto.sns.connect_to_region(
            "ap-southeast-1",
            aws_access_key_id=access_id,
            aws_secret_access_key=secret_key,
        )
        alert.topic = topic
        return alert

    def send(self, message, subject=None):
        logger.info('SNSAlert: {0}'.format(message))
        self.conn.publish(self.topic, message, subject)
