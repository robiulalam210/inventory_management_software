# reports/utils.py
from rest_framework.response import Response

def custom_response(success=True, message="", data=None, status_code=200):
    """
    Standard response format for all APIs.

    :param success: bool, indicates success or failure
    :param message: str, human-readable message
    :param data: any, the response payload
    :param status_code: int, HTTP status code
    :return: DRF Response object
    """
    return Response({
        "status": success,
        "message": message,
        "data": data
    }, status=status_code)
