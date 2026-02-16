from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DashboardUserPagination(PageNumberPagination):
    page_size = 20                 # default items per page
    page_size_query_param = "page_size"  # allow client to override
    max_page_size = 100            # safety limit
    page_query_param = "page"      # ?page=2

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })
