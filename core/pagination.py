from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 30
    page_query_param = 'page'

    def get_paginated_response(self, data, message="Data fetched successfully."):
        return Response({
            'status': True,
            'message': message,
            'data': {
                'count': self.page.paginator.count,
                'total_pages': self.page.paginator.num_pages,
                'current_page': self.page.number,
                'page_size': self.page_size,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        }, status=status.HTTP_200_OK)

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'status': {
                    'type': 'boolean',
                    'example': True
                },
                'message': {
                    'type': 'string',
                    'example': 'Data fetched successfully.'
                },
                'data': {
                    'type': 'object',
                    'properties': {
                        'count': {
                            'type': 'integer',
                            'example': 100
                        },
                        'total_pages': {
                            'type': 'integer',
                            'example': 10
                        },
                        'current_page': {
                            'type': 'integer',
                            'example': 1
                        },
                        'page_size': {
                            'type': 'integer',
                            'example': 10
                        },
                        'next': {
                            'type': 'string',
                            'nullable': True,
                            'example': 'http://api.example.org/accounts/?page=2'
                        },
                        'previous': {
                            'type': 'string',
                            'nullable': True,
                            'example': None
                        },
                        'results': schema
                    }
                }
            }
        }