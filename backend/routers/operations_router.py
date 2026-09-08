from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User
from operational_models import PersonnelDevice, PersonnelGPSObservation, PersonnelPresence
from routers.auth_router import get_current_user
from crawler.models.raw_record import RawRecord

router = APIRouter(prefix="/api/operations", tags=["Operational Geography"])

CHANDIGARH_BOUNDS = (30.64, 30.82, 76.68, 76.90)

ZONES = [
    {"id": "north_chandigarh", "name": "North Chandigarh", "bounds": [[30.78, 76.70], [30.82, 76.86]], "aliases": ["north chandigarh"]},
    {"id": "manimajra", "name": "North-East / Manimajra", "bounds": [[30.74, 76.82], [30.82, 76.90]], "aliases": ["manimajra", "manimajra"]},
    {"id": "sukhna_capitol", "name": "Sukhna / Capitol Area", "bounds": [[30.72, 76.77], [30.79, 76.86]], "aliases": ["sukhna", "sukhna lake", "capitol complex"]},
    {"id": "sector_17", "name": "Central Sector 17", "bounds": [[30.735, 76.775], [30.755, 76.795]], "aliases": ["sector 17", "sector-17", "sec 17"]},
    {"id": "central_west", "name": "Central-West", "bounds": [[30.70, 76.70], [30.75, 76.775]], "aliases": ["central west"]},
    {"id": "sector_22", "name": "Sector 22 / Transit", "bounds": [[30.70, 76.765], [30.735, 76.795]], "aliases": ["sector 22", "sector-22", "sec 22"]},
    {"id": "sector_34", "name": "Sector 34 / 35", "bounds": [[30.675, 76.735], [30.71, 76.78]], "aliases": ["sector 34", "sector-34", "sector 35", "sector-35"]},
    {"id": "sector_43", "name": "Sector 43 / ISBT", "bounds": [[30.655, 76.735], [30.69, 76.78]], "aliases": ["sector 43", "sector-43", "isbt 43"]},
    {"id": "south_chandigarh", "name": "South Chandigarh", "bounds": [[30.62, 76.70], [30.68, 76.78]], "aliases": ["south chandigarh"]},
    {"id": "south_east", "name": "South-East", "bounds": [[30.64, 76.78], [30.70, 76.90]], "aliases": ["south east"]},
    {"id": "south_west", "name": "South-West", "bounds": [[30.64, 76.68], [30.70, 76.74]], "aliases": ["south west"]},
    {"id": "industrial_railway", "name": "Industrial / Railway Corridor", "bounds": [[30.70, 76.68], [30.76, 76.74]], "aliases": ["industrial area", "railway station"]},
]


class PresenceHeartbeat(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=CHANDIGARH_BOUNDS[0], le=CHANDIGARH_BOUNDS[1])
    longitude: float = Field(ge=CHANDIGARH_BOUNDS[2], le=CHANDIGARH_BOUNDS[3])
    accuracy_m: Optional[float] = Field(default=None, ge=0, le=5000)
    captured_at: datetime
    duty_status: str = Field(default="ON_DUTY", max_length=40)


def _zone_for_point(latitude: float, longitude: float):
    for zone in ZONES:
        south_west, north_east = zone["bounds"]
        if south_west[0] <= latitude <= north_east[0] and south_west[1] <= longitude <= north_east[1]:
            return zone
    return None


def _zone_for_text(text: str):
    lowered = text.lower()
    for zone in ZONES:
        matches = [alias for alias in zone["aliases"] if alias in lowered]
        if matches:
            return zone, matches
    return None, []


def _freshness(captured_at: datetime) -> str:
    age = (datetime.now(timezone.utc) - _as_utc(captured_at)).total_seconds()
    if age <= 120:
        return "fresh"
    if age <= 600:
        return "aging"
    return "stale"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ensure_demo_devices(db: Session) -> None:
    if db.query(PersonnelDevice).count() > 0:
        return
    users = db.query(User).filter(User.account_status == "ACTIVE").limit(3).all()
    samples = [(30.7412, 76.7824, "sector_17"), (30.6868, 76.8013, "sector_34"), (30.7162, 76.8486, "manimajra")]
    for index, (latitude, longitude, zone_id) in enumerate(samples):
        user = users[index] if index < len(users) else None
        device = PersonnelDevice(
            device_id=f"demo-device-{index + 1:03d}",
            user_id=user.id if user else None,
            display_name=user.full_name if user else f"Patrol Unit {index + 1}",
            unit=user.unit if user else "Chandigarh Police",
            is_demo=True,
        )
        db.add(device)
        db.flush()
        captured_at = datetime.now(timezone.utc) - timedelta(seconds=index * 45)
        db.add(PersonnelGPSObservation(device_id=device.id, latitude=latitude, longitude=longitude, accuracy_m=18, duty_status="ON_DUTY", captured_at=captured_at))
        db.add(PersonnelPresence(device_id=device.id, latitude=latitude, longitude=longitude, zone_id=zone_id, accuracy_m=18, duty_status="ON_DUTY", captured_at=captured_at))
    db.commit()


@router.get("/presence")
def get_presence(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_demo_devices(db)
    rows = db.query(PersonnelPresence, PersonnelDevice).join(PersonnelDevice, PersonnelDevice.id == PersonnelPresence.device_id).filter(PersonnelDevice.is_active.is_(True)).all()
    now = datetime.now(timezone.utc)
    return {"items": [{
        "device_id": device.device_id,
        "display_name": device.display_name,
        "unit": device.unit,
        "latitude": presence.latitude,
        "longitude": presence.longitude,
        "zone_id": presence.zone_id,
        "accuracy_m": presence.accuracy_m,
        "duty_status": presence.duty_status,
        "captured_at": presence.captured_at.isoformat(),
        "age_seconds": max(0, int((now - presence.captured_at).total_seconds())),
        "freshness": _freshness(presence.captured_at),
        "is_demo": device.is_demo,
    } for presence, device in rows]}


@router.post("/presence/heartbeat")
def heartbeat(payload: PresenceHeartbeat, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    captured_at = _as_utc(payload.captured_at)
    if captured_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Captured time cannot be more than five minutes in the future")
    device = db.query(PersonnelDevice).filter(PersonnelDevice.device_id == payload.device_id, PersonnelDevice.is_active.is_(True)).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active personnel device not found")
    zone = _zone_for_point(payload.latitude, payload.longitude)
    observation = PersonnelGPSObservation(device_id=device.id, latitude=payload.latitude, longitude=payload.longitude, accuracy_m=payload.accuracy_m, duty_status=payload.duty_status, captured_at=captured_at)
    presence = db.query(PersonnelPresence).filter(PersonnelPresence.device_id == device.id).first()
    if not presence:
        presence = PersonnelPresence(device_id=device.id, latitude=payload.latitude, longitude=payload.longitude, captured_at=captured_at)
        db.add(presence)
    presence.latitude = payload.latitude
    presence.longitude = payload.longitude
    presence.zone_id = zone["id"] if zone else None
    presence.accuracy_m = payload.accuracy_m
    presence.duty_status = payload.duty_status
    presence.captured_at = captured_at
    db.add(observation)
    db.commit()
    return {"accepted": True, "device_id": payload.device_id, "zone_id": zone["id"] if zone else None, "captured_at": captured_at.isoformat()}


@router.get("/zones")
def get_zones(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    records = db.query(RawRecord.cleaned_text, RawRecord.raw_text, RawRecord.fetched_at, RawRecord.relevance_confidence).filter(RawRecord.fetched_at >= since).all()
    summaries = {zone["id"]: {"signal_count": 0, "max_confidence": 0, "matched_aliases": set()} for zone in ZONES}
    for cleaned_text, raw_text, fetched_at, confidence in records:
        zone, aliases = _zone_for_text(f"{cleaned_text or ''} {raw_text or ''}")
        if zone:
            summary = summaries[zone["id"]]
            summary["signal_count"] += 1
            summary["max_confidence"] = max(summary["max_confidence"], float(confidence or 0))
            summary["matched_aliases"].update(aliases)
    return {"zones": [{**zone, "signal_count": summaries[zone["id"]]["signal_count"], "max_confidence": summaries[zone["id"]]["max_confidence"], "matched_aliases": sorted(summaries[zone["id"]]["matched_aliases"])} for zone in ZONES]}
