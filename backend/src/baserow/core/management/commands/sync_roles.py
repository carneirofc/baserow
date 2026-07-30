from django.core.management.base import BaseCommand

from baserow.core.roles.config import get_declared_roles
from baserow.core.roles.handler import sync_declared_roles


class Command(BaseCommand):
    help = (
        "Reconciles the roles declared in the BASEROW_ROLES environment variable into "
        "the database. Runs automatically after every migrate; run it manually after "
        "creating a workspace a declared role refers to. Roles that are no longer "
        "declared are left untouched."
    )

    def handle(self, *args, **options):
        configs = get_declared_roles()
        if not configs:
            self.stdout.write("No roles declared in BASEROW_ROLES; nothing to do.")
            return

        sync_declared_roles(configs)
        self.stdout.write(
            self.style.SUCCESS(f"Synced {len(configs)} declared role(s).")
        )
