"""Schematy AI Assistant (chatbot) — Story 6.14 (FR66)."""

from pydantic import BaseModel, ConfigDict, Field

#: Maksymalna długość pojedynczego pytania użytkownika.
MAX_MESSAGE_LENGTH = 4000


class ChatContext(BaseModel):
    """Kontekst widoku, z którego użytkownik zadaje pytanie."""

    model_config = ConfigDict(extra="ignore")

    project_id: str | None = None
    view: str | None = None


class ChatMessageRequest(BaseModel):
    """Pytanie użytkownika do asystenta."""

    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: str | None = None
    context: ChatContext | None = None
