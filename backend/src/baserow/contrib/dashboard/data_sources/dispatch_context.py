from typing import TYPE_CHECKING

from django.http import HttpRequest

from baserow.core.services.dispatch_context import DispatchContext

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class DashboardDispatchContext(DispatchContext):
    own_properties = [
        "request",
        "workspace",
    ]

    def __init__(
        self,
        request: HttpRequest,
        workspace: "Workspace",
    ):
        self.request = request

        super().__init__(workspace)

    def range(self, service):
        offset, count = 0, None
        return [offset, count]

    def is_publicly_searchable(self):
        return False

    def search_query(self):
        return None

    def searchable_fields(self):
        return []

    def is_publicly_filterable(self):
        return False

    def filters(self):
        return None

    def is_publicly_sortable(self):
        return False

    def sortings(self):
        return None

    def public_allowed_properties(self):
        return None

    def validate_filter_search_sort_fields(self): ...
