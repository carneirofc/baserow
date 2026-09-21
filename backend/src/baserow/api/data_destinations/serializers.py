from rest_framework import serializers

from baserow.core.data_destinations.config import ALL_PURPOSES


class DataDestinationSerializer(serializers.Serializer):
    name = serializers.CharField(help_text="The name destinations are referenced by.")
    type = serializers.CharField(
        help_text="The kind of storage: s3, azure or filesystem."
    )
    purposes = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_PURPOSES),
        help_text="What the destination may be used for.",
    )
