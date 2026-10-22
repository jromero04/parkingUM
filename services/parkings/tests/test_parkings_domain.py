import uuid
from types import SimpleNamespace

import pytest
from fastapi import Response

from app.errors import ApiError
from app.models import OutboxEvent, Spot
from app.routes import assign_spot, release_assignment
from app.schemas import AssignmentCreate

from conftest import PARKING_ID, SPOT_ID


def request():
    return SimpleNamespace(state=SimpleNamespace(correlation_id=str(uuid.uuid4())))


def payload():
    return AssignmentCreate(
        parking_id=PARKING_ID,
        spot_id=SPOT_ID,
        operation_id=uuid.uuid4(),
    )


def test_assignment_domain_is_atomic_and_idempotent(db_session):
    reservation_id = uuid.uuid4()
    operation = payload()
    response = Response()
    created = assign_spot(reservation_id, operation, request(), response, db_session)
    assert response.status_code == 201
    assert created.status == "assigned"

    repeated_response = Response()
    repeated = assign_spot(reservation_id, operation, request(), repeated_response, db_session)
    assert repeated_response.status_code == 200
    assert repeated.reservation_id == reservation_id

    with pytest.raises(ApiError) as conflict:
        assign_spot(uuid.uuid4(), payload(), request(), Response(), db_session)
    assert conflict.value.code == "SPOT_UNAVAILABLE"
    assert conflict.value.details["reason"] == "assigned"
    assert db_session.query(OutboxEvent).count() == 1


def test_release_closes_before_create_and_preserves_physical_state(db_session):
    reservation_id = uuid.uuid4()
    spot = db_session.get(Spot, SPOT_ID)
    spot.physical_occupied = True
    db_session.commit()

    released = release_assignment(
        reservation_id,
        request(),
        db_session,
        idempotency_key=str(uuid.uuid4()),
    )
    assert released.status == "released"
    with pytest.raises(ApiError) as late:
        assign_spot(reservation_id, payload(), request(), Response(), db_session)
    assert late.value.code == "ASSIGNMENT_CLOSED"
    db_session.refresh(spot)
    assert spot.physical_occupied is True
    assert spot.assigned_reservation_id is None
