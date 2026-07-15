from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic_ai.messages import UserContent


@runtime_checkable
class AIFile(Protocol):
    """
    Structural type for a file passed to a ``GenerativeAIModelType``.

    Implementations wrap a serialized user file dict from a file field cell and
    expose its content lazily through ``read_content``. ``content`` and
    ``provider_file_id`` are populated by
    :meth:`GenerativeAIModelType.prepare_files`; ``provider_file_id`` is only set
    when the file was uploaded to the provider and therefore needs cleaning up
    afterwards.
    """

    name: str
    original_name: str
    size: int
    mime_type: str

    content: Optional[UserContent]
    provider_file_id: Optional[str]

    def read_content(self) -> bytes: ...
