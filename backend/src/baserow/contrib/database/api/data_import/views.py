from django.conf import settings

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.database.api.tables.errors import ERROR_TABLE_DOES_NOT_EXIST
from baserow.contrib.database.data_import.models import TableImportRecord
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler

from .serializers import TableImportRecordSerializer


class TableImportRecordsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the table to list the import records of.",
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The maximum number of import records to return.",
            ),
            OpenApiParameter(
                name="offset",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The offset of the import records to return.",
            ),
        ],
        tags=["Database tables"],
        operation_id="list_database_table_import_records",
        description=(
            "Lists every file import that has touched the rows of the table with the "
            "given table_id, newest first. These records are kept independently of "
            "the import jobs that produced them, so they remain available after the "
            "jobs have been cleaned up."
        ),
        responses={
            200: get_example_pagination_serializer_class(TableImportRecordSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, table_id: int) -> Response:
        paginator = LimitOffsetPagination()
        paginator.max_limit = settings.ROW_PAGE_SIZE_LIMIT
        paginator.default_limit = settings.ROW_PAGE_SIZE_LIMIT

        table = TableHandler().get_table(table_id)
        CoreHandler().check_permissions(
            request.user,
            ReadDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        records = TableImportRecord.objects.filter(table_id=table.id)
        page = paginator.paginate_queryset(records, request, self)
        return paginator.get_paginated_response(
            TableImportRecordSerializer(page, many=True).data
        )
