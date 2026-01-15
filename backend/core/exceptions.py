"""
Custom Exception Handler
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': get_error_message(response.data),
                'details': response.data
            }
        }
        response.data = custom_response
    else:
        # Handle unexpected exceptions
        logger.exception(f"Unhandled exception: {exc}")
        response = Response(
            {
                'success': False,
                'error': {
                    'code': 500,
                    'message': 'An unexpected error occurred',
                    'details': str(exc) if hasattr(exc, '__str__') else 'Unknown error'
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return response


def get_error_message(data):
    """Extract readable error message from DRF error response."""
    if isinstance(data, dict):
        # Check for common DRF error keys
        if 'detail' in data:
            return str(data['detail'])
        if 'non_field_errors' in data:
            return str(data['non_field_errors'][0])
        # Return first field error
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                return f"{key}: {value[0]}"
            return f"{key}: {value}"
    elif isinstance(data, list) and len(data) > 0:
        return str(data[0])
    return str(data)
