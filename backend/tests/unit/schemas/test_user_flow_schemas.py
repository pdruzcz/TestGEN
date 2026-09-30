"""Regression tests for user-flow schemas (Story 3.7 / 3-11-domknięcie).

Walidacja ``FlowStepOut`` z **prawdziwego ORM** ``FlowStep`` — SimpleNamespace
w testach integracyjnych nie ma atrybutu ``metadata``, więc nie wychwyci
kolizji z rezerwowym ``sqlalchemy.MetaData`` (bug: GET /uml/flows → 500).
"""

from app.models.user_flow import FlowStep
from app.schemas.user_flow import FlowStepOut


def test_flow_step_out_from_real_orm_flow_step() -> None:
    """from_attributes na ORM FlowStep czyta ``meta``, nie ``Base.metadata``."""
    step = FlowStep(
        sequence=1,
        action="Kliknij Zaloguj",
        actor="Klient",
        source="native",
        meta={"relation_type": "include"},
    )

    out = FlowStepOut.model_validate(step)

    assert out.action == "Kliknij Zaloguj"
    assert out.source == "native"
    assert out.metadata == {"relation_type": "include"}


def test_flow_step_out_accepts_metadata_kwarg() -> None:
    """Konstrukcja jawna (task cross-diagram) nadal działa bez zmian."""
    out = FlowStepOut(sequence=2, action="Krok", metadata={"branch_label": "tak"})

    assert out.metadata == {"branch_label": "tak"}


def test_flow_step_out_orm_without_meta_defaults_to_none() -> None:
    step = FlowStep(sequence=1, action="Krok", source="native")

    assert FlowStepOut.model_validate(step).metadata is None
