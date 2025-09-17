import hashlib
import hmac
from time import time

from django.conf import settings
from rest_framework.permissions import BasePermission


class isSlackRequestSigned(BasePermission):
    def has_permission(self, request, view):
        if not settings.SLACK_SIGNING_SECRET:
            return False

        # Each request comes with request timestamp and request signature
        # return false if the timestamp is out of range
        req_timestamp = request.headers.get("X-Slack-Request-Timestamp")
        if req_timestamp is None or abs(time() - int(req_timestamp)) > 60 * 5:
            return False

        # Verify the request signature using the app's signing secret
        # return false if the signature can't be verified
        req_signature = request.headers.get("X-Slack-Signature")
        if req_signature is None:
            return False

        # Verify the request signature of the request sent from Slack
        # Generate a new hash using the app's signing secret and request data

        # Compare the generated hash and incoming request signature
        # Python 2.7.6 doesn't support compare_digest
        # It's recommended to use Python 2.7.7+
        # noqa See https://docs.python.org/2/whatsnew/2.7.html#pep-466-network-security-enhancements-for-python-2-7
        # req = str.encode('v0:' + str(req_timestamp) + ':') + request.get_data()
        req = str.encode("v0:" + str(req_timestamp) + ":") + request.body
        request_hash = (
            "v0="
            + hmac.new(str.encode(settings.SLACK_SIGNING_SECRET), req, hashlib.sha256).hexdigest()
        )

        if hasattr(hmac, "compare_digest"):
            return hmac.compare_digest(request_hash, req_signature)
        else:
            if len(request_hash) != len(req_signature):
                return False
            result = 0
            if isinstance(request_hash, bytes) and isinstance(req_signature, bytes):
                for x, y in zip(request_hash, req_signature):
                    result |= x ^ y
            else:
                for x, y in zip(request_hash, req_signature):
                    result |= ord(x) ^ ord(y)
            return result == 0
