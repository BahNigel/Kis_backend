from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            "meta": {
                "count": self.page.paginator.count,
                "page_size": self.get_page_size(self.request),
                "current": self.page.number,
                "total_pages": self.page.paginator.num_pages,
            },
            "results": data
        })
