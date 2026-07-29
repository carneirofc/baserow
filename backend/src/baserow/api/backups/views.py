from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.api_clients.authentication import (
    ApiClientAuthentication,
    HasApiClientScope,
)
from baserow.api.backups.errors import (
    ERROR_BACKUP_SCHEDULE_DOES_NOT_EXIST,
    ERROR_INVALID_BACKUP_SCHEDULE_CRON,
)
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.import_export.errors import (
    ERROR_APPLICATION_IDS_NOT_FOUND,
    ERROR_RESOURCE_DOES_NOT_EXIST,
    ERROR_RESOURCE_IS_BEING_IMPORTED,
    ERROR_RESOURCE_IS_INVALID,
)
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import get_error_schema
from baserow.core.backups.exceptions import (
    BackupScheduleDoesNotExist,
    InvalidBackupScheduleCron,
)
from baserow.core.backups.handler import BackupHandler
from baserow.core.backups.schedule_handler import BackupScheduleHandler
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.handler import CoreHandler
from baserow.core.import_export.exceptions import (
    ImportExportApplicationIdsNotFound,
    ImportExportResourceDoesNotExist,
    ImportExportResourceInBeingImported,
    ImportExportResourceInvalidFile,
)
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.registries import job_type_registry

from .serializers import (
    BackupScheduleSerializer,
    CreateBackupScheduleSerializer,
    CreateBackupSerializer,
    ListBackupsSerializer,
    RestoreBackupSerializer,
    UpdateBackupScheduleSerializer,
)

COMMON_EXCEPTIONS = {
    WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
    ApplicationDoesNotExist: ERROR_RESOURCE_DOES_NOT_EXIST,
    ImportExportResourceDoesNotExist: ERROR_RESOURCE_DOES_NOT_EXIST,
    ImportExportResourceInvalidFile: ERROR_RESOURCE_IS_INVALID,
    ImportExportResourceInBeingImported: ERROR_RESOURCE_IS_BEING_IMPORTED,
    ImportExportApplicationIdsNotFound: ERROR_APPLICATION_IDS_NOT_FOUND,
    BackupScheduleDoesNotExist: ERROR_BACKUP_SCHEDULE_DOES_NOT_EXIST,
    InvalidBackupScheduleCron: ERROR_INVALID_BACKUP_SCHEDULE_CRON,
}

WORKSPACE_ID_PARAMETER = OpenApiParameter(
    name="workspace_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the workspace.",
    required=True,
)


class BackupsView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {"GET": "backup.read"}

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="list_backups",
        description=(
            "Lists the finished backups of a workspace that were created by the "
            "authenticated user, most recent first. Each entry carries the name of the "
            "archive and the URL to download it from."
        ),
        responses={
            200: ListBackupsSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    def get(self, request, workspace_id: int):
        backups = BackupHandler().list_backups(request.user, workspace_id)
        return Response(ListBackupsSerializer({"results": backups}).data)


class StartBackupView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {"POST": "backup.write"}

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="start_backup",
        description=(
            "Starts a backup of a workspace. Leave `application_ids` out to back up "
            "the whole workspace, or pass one or more ids to back up only those "
            "applications. The response is a job, poll `/api/jobs/{job_id}/` until it "
            "finishes and the archive becomes available through the list endpoint."
        ),
        request=CreateBackupSerializer,
        responses={
            202: JobSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {**COMMON_EXCEPTIONS, MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED}
    )
    @validate_body(CreateBackupSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data, workspace_id: int):
        job = BackupHandler().start_backup(
            request.user,
            workspace_id,
            application_ids=data.get("application_ids"),
            only_structure=data.get("only_structure", False),
        )
        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class BackupView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {"GET": "backup.read", "DELETE": "backup.write"}

    @extend_schema(
        parameters=[
            WORKSPACE_ID_PARAMETER,
            OpenApiParameter(
                name="resource_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the backup resource.",
                required=True,
            ),
        ],
        tags=["Backups"],
        operation_id="get_backup",
        description="Returns a single backup, including its download URL.",
        responses={
            200: ListBackupsSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(
                ["ERROR_GROUP_DOES_NOT_EXIST", "ERROR_RESOURCE_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    def get(self, request, workspace_id: int, resource_id: int):
        backup = BackupHandler().get_backup(request.user, workspace_id, resource_id)
        serializer = job_type_registry.get_serializer(backup, JobSerializer)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            WORKSPACE_ID_PARAMETER,
            OpenApiParameter(
                name="resource_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the backup resource to delete.",
                required=True,
            ),
        ],
        tags=["Backups"],
        operation_id="delete_backup",
        description=(
            "Marks the archive of a backup for deletion. A periodic task removes the "
            "files afterwards."
        ),
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_RESOURCE_IS_BEING_IMPORTED"]
            ),
            404: get_error_schema(
                ["ERROR_GROUP_DOES_NOT_EXIST", "ERROR_RESOURCE_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    @transaction.atomic
    def delete(self, request, workspace_id: int, resource_id: int):
        handler = BackupHandler()
        # Makes sure the resource really is a backup of this workspace before it is
        # removed, the handler below only checks ownership.
        handler.get_backup(request.user, workspace_id, resource_id)
        handler.delete_backup(request.user, resource_id)
        return Response(status=HTTP_204_NO_CONTENT)


class RestoreBackupView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {"POST": "backup.restore"}

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="restore_backup",
        description=(
            "Restores a backup into a workspace. The applications in the archive are "
            "installed as new applications, an existing application is never "
            "overwritten in place. The response is a job, poll `/api/jobs/{job_id}/` "
            "for its progress.\n\nTo restore an archive that was produced elsewhere, "
            "upload it first through "
            "`/api/workspaces/{workspace_id}/import/upload-file/` and pass the "
            "resulting resource id here."
        ),
        request=RestoreBackupSerializer,
        responses={
            202: JobSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_RESOURCE_IS_INVALID",
                    "ERROR_APPLICATION_IDS_NOT_FOUND",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(
                ["ERROR_GROUP_DOES_NOT_EXIST", "ERROR_RESOURCE_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {**COMMON_EXCEPTIONS, MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED}
    )
    @validate_body(RestoreBackupSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data, workspace_id: int):
        job = BackupHandler().start_restore(
            request.user,
            workspace_id,
            data["resource_id"],
            application_ids=data.get("application_ids"),
        )
        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class BackupSchedulesView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {"GET": "schedule.read", "POST": "schedule.write"}

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="list_backup_schedules",
        description="Lists the backup schedules of a workspace.",
        responses={
            200: BackupScheduleSerializer(many=True),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    def get(self, request, workspace_id: int):
        schedules = BackupScheduleHandler().list_schedules(request.user, workspace_id)
        return Response(BackupScheduleSerializer(schedules, many=True).data)

    @extend_schema(
        parameters=[WORKSPACE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="create_backup_schedule",
        description=(
            "Creates a recurring backup of a workspace. The schedule runs on behalf of "
            "the user that created it. Set `keep_last` or `keep_days` to have older "
            "backups cleaned up automatically."
        ),
        request=CreateBackupScheduleSerializer,
        responses={
            200: BackupScheduleSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INVALID_BACKUP_SCHEDULE_CRON",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    @validate_body(CreateBackupScheduleSerializer, return_validated=True)
    @transaction.atomic
    def post(self, request, data, workspace_id: int):
        workspace = CoreHandler().get_workspace(workspace_id)
        schedule = BackupScheduleHandler().create_schedule(
            request.user,
            workspace,
            name=data["name"],
            cron=data["cron"],
            tz_name=data["timezone"],
            application_ids=data["application_ids"],
            only_structure=data["only_structure"],
            keep_last=data["keep_last"],
            keep_days=data["keep_days"],
            is_active=data["is_active"],
        )
        return Response(BackupScheduleSerializer(schedule).data)


SCHEDULE_ID_PARAMETER = OpenApiParameter(
    name="schedule_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the backup schedule.",
    required=True,
)


class BackupScheduleView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {
        "GET": "schedule.read",
        "PATCH": "schedule.write",
        "DELETE": "schedule.write",
    }

    @extend_schema(
        parameters=[SCHEDULE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="get_backup_schedule",
        description="Returns a single backup schedule.",
        responses={
            200: BackupScheduleSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_BACKUP_SCHEDULE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    def get(self, request, schedule_id: int):
        schedule = BackupScheduleHandler().get_schedule(request.user, schedule_id)
        return Response(BackupScheduleSerializer(schedule).data)

    @extend_schema(
        parameters=[SCHEDULE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="update_backup_schedule",
        description=(
            "Updates a backup schedule. Changing the cron expression or the timezone "
            "recomputes when the schedule next runs."
        ),
        request=UpdateBackupScheduleSerializer,
        responses={
            200: BackupScheduleSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INVALID_BACKUP_SCHEDULE_CRON",
                ]
            ),
            404: get_error_schema(["ERROR_BACKUP_SCHEDULE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    @validate_body(UpdateBackupScheduleSerializer, return_validated=True)
    @transaction.atomic
    def patch(self, request, data, schedule_id: int):
        handler = BackupScheduleHandler()
        schedule = handler.get_schedule(request.user, schedule_id, for_update=True)
        schedule = handler.update_schedule(request.user, schedule, **data)
        return Response(BackupScheduleSerializer(schedule).data)

    @extend_schema(
        parameters=[SCHEDULE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="delete_backup_schedule",
        description=(
            "Deletes a backup schedule. The backups it already made are kept."
        ),
        responses={
            204: None,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_BACKUP_SCHEDULE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(COMMON_EXCEPTIONS)
    @transaction.atomic
    def delete(self, request, schedule_id: int):
        handler = BackupScheduleHandler()
        schedule = handler.get_schedule(request.user, schedule_id)
        handler.delete_schedule(request.user, schedule)
        return Response(status=HTTP_204_NO_CONTENT)


class RunBackupScheduleView(APIView):
    authentication_classes = APIView.authentication_classes + [ApiClientAuthentication]
    permission_classes = (IsAuthenticated, HasApiClientScope)
    api_client_scopes = {"POST": "schedule.write"}

    @extend_schema(
        parameters=[SCHEDULE_ID_PARAMETER],
        tags=["Backups"],
        operation_id="run_backup_schedule",
        description=(
            "Runs a backup schedule right now, without waiting for its next due "
            "moment and without changing it."
        ),
        request=None,
        responses={
            202: JobSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_MAX_JOB_COUNT_EXCEEDED"]
            ),
            404: get_error_schema(["ERROR_BACKUP_SCHEDULE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {**COMMON_EXCEPTIONS, MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED}
    )
    @transaction.atomic
    def post(self, request, schedule_id: int):
        handler = BackupScheduleHandler()
        schedule = handler.get_schedule(request.user, schedule_id)
        job = handler.run_schedule(schedule, requested_by=request.user)
        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
