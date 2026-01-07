from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class DeviceBoundJWTAuthentication(JWTAuthentication):
    """
    Enforce device-bound access tokens.
    Clients must send X-Device-Id to match the device_id claim in the token.
    Internal service calls can bypass by using X-Internal-Auth.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return None

        user, validated_token = result
        if request.headers.get("X-Internal-Auth"):
            return (user, validated_token)

        token_device_id = validated_token.get("device_id")
        if not token_device_id:
            raise AuthenticationFailed("Device-bound token required")

        header_device_id = (
            request.headers.get("X-Device-Id")
            or request.headers.get("X-Device-ID")
            or request.headers.get("X-DeviceId")
        )
        if not header_device_id:
            raise AuthenticationFailed("Missing X-Device-Id")

        if str(token_device_id) != str(header_device_id):
            raise AuthenticationFailed("Device mismatch")

        return (user, validated_token)
