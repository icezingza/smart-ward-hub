from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from statistics import pstdev
from threading import RLock
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session

from config import settings
from edge_runtime import EdgeTelemetryStore
from device_trust import public_key_fingerprint, verify_device_signature
from edge_controls import (
    AuditSink,
    FileAnchorStore,
    SlidingWindowRateLimiter,
    reset_request_id,
    set_request_id,
)
from security import require_scope

from database import Base, SessionLocal, engine, get_db
import models
import schemas


RATE_LIMITER = SlidingWindowRateLimiter(limit=settings.rate_limit_per_minute, window_seconds=60)
AUDIT_SINK = AuditSink(path=settings.audit_log_path)
ANCHOR_STORE = FileAnchorStore(
    path=settings.forensic_anchor_path,
    source_root=Path(__file__).resolve().parent,
)
HANDOVER_SYNC_LOCK = RLock()


if settings.auto_create_db:
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="IPD Smart Sentinel: Ward Edge Hub API",
    description="Sovereign Edge-First Patient Monitoring Hub",
    version="2.0.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Device-Key-ID",
            "X-Device-Signature",
        ],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    token = set_request_id(request_id)
    client_key = request.client.host if request.client else "unknown"
    try:
        allowed, retry_after = RATE_LIMITER.allow(client_key)
        if not allowed:
            AUDIT_SINK.record(
                "request.rate_limit",
                "denied",
                resource_type="http_request",
                resource_id=request.url.path,
                details={"method": request.method, "retry_after": retry_after},
            )
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded."},
                headers={"Retry-After": str(retry_after)},
            )
        else:
            response = await call_next(request)
            if response.status_code >= 400:
                AUDIT_SINK.record(
                    "http.request",
                    "failure",
                    resource_type="http_request",
                    resource_id=request.url.path,
                    details={"method": request.method, "status_code": response.status_code},
                )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        reset_request_id(token)

ACTIVE_PAIRINGS_CACHE: dict[str, dict[str, Any]] = {}
RING_BUFFER_MAX_SAMPLES = settings.telemetry_buffer_max_samples
TELEMETRY_STORE = EdgeTelemetryStore(
    max_samples=RING_BUFFER_MAX_SAMPLES,
    state_path=settings.telemetry_state_path,
    checkpoint_every=settings.telemetry_checkpoint_every,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _active_device_credential(db: Session, device_id: str):
    return db.query(models.DeviceCredential).filter(
        models.DeviceCredential.device_id == device_id,
        models.DeviceCredential.status == "ACTIVE",
    ).first()


def verify_ingress_device_trust(
    packet: schemas.TelemetryPacket,
    http_request: Request,
    db: Session,
) -> str:
    """Verify an optional signed envelope without changing TelemetryPacket v1."""
    if settings.device_trust_mode == "disabled":
        return "DISABLED"

    key_id = http_request.headers.get("X-Device-Key-ID")
    signature = http_request.headers.get("X-Device-Signature")
    if not key_id or not signature:
        outcome = "missing_signature"
        AUDIT_SINK.record(
            "device_trust.verify",
            "unverified",
            resource_type="device",
            resource_id=packet.device_id,
            details={"reason": outcome, "mode": settings.device_trust_mode},
        )
        if settings.device_trust_mode == "enforce":
            raise HTTPException(status_code=401, detail="Device signature required.")
        return "UNVERIFIED"

    credential = db.query(models.DeviceCredential).filter(
        models.DeviceCredential.device_id == packet.device_id,
        models.DeviceCredential.key_id == key_id,
    ).first()
    if credential is None:
        outcome = "unknown_key_id"
        valid = False
    else:
        verification = verify_device_signature(
            packet.model_dump(),
            public_key_b64=credential.public_key_b64,
            algorithm=credential.algorithm,
            signature_b64=signature,
            timestamp_skew_seconds=settings.device_trust_clock_skew_seconds,
            expires_at=credential.expires_at,
            status=credential.status,
        )
        outcome = verification.reason
        valid = verification.valid

    if not valid:
        AUDIT_SINK.record(
            "device_trust.verify",
            "rejected" if settings.device_trust_mode == "enforce" else "unverified",
            resource_type="device",
            resource_id=packet.device_id,
            details={"key_id": key_id, "reason": outcome, "mode": settings.device_trust_mode},
        )
        if settings.device_trust_mode == "enforce":
            raise HTTPException(status_code=401, detail="Device signature verification failed.")
        return "UNVERIFIED"

    AUDIT_SINK.record(
        "device_trust.verify",
        "success",
        resource_type="device",
        resource_id=packet.device_id,
        details={"key_id": key_id, "mode": settings.device_trust_mode},
    )
    return "VERIFIED"


SESSION_DIGEST_GENESIS = "0" * 64


def active_session_for_device(db: Session, device_id: str) -> models.WardSession | None:
    return db.query(models.WardSession).filter(
        models.WardSession.device_id == device_id,
        models.WardSession.status.in_(["ACTIVE", "RESET_PENDING", "INCIDENT_FROZEN"]),
    ).order_by(models.WardSession.started_at.desc()).first()


def create_session_close_digest(
    db: Session,
    session: models.WardSession,
    samples: list[dict[str, Any]],
) -> models.SessionCloseDigest:
    existing = db.query(models.SessionCloseDigest).filter(
        models.SessionCloseDigest.session_id == session.session_id,
    ).first()
    if existing is not None:
        return existing
    ordered = sorted(samples, key=lambda item: item.get("sequence", -1))
    summary = {
        "session_id": session.session_id,
        "device_id": session.device_id,
        "bed_no": session.bed_no,
        "sample_count": len(ordered),
        "first_sequence": ordered[0].get("sequence") if ordered else None,
        "last_sequence": ordered[-1].get("sequence") if ordered else None,
        "first_timestamp": str(ordered[0].get("timestamp")) if ordered else None,
        "last_timestamp": str(ordered[-1].get("timestamp")) if ordered else None,
    }
    serialized = json.dumps(summary, sort_keys=True, separators=(",", ":"), default=str)
    previous = db.query(models.SessionCloseDigest).order_by(models.SessionCloseDigest.id.desc()).first()
    previous_hash = previous.digest_hash if previous else SESSION_DIGEST_GENESIS
    digest_hash = hashlib.sha256(f"{previous_hash}:{serialized}".encode("utf-8")).hexdigest()
    digest = models.SessionCloseDigest(
        session_id=session.session_id,
        device_id=session.device_id,
        patient_token=session.patient_token,
        bed_no=session.bed_no,
        sample_count=len(ordered),
        first_sequence=ordered[0].get("sequence") if ordered else None,
        last_sequence=ordered[-1].get("sequence") if ordered else None,
        digest_hash=digest_hash,
        previous_digest_hash=previous_hash,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)
    AUDIT_SINK.record(
        "session.close_digest",
        "success",
        resource_type="ward_session",
        resource_id=session.session_id,
        details={
            "sample_count": digest.sample_count,
            "first_sequence": digest.first_sequence,
            "last_sequence": digest.last_sequence,
            "digest_hash": digest.digest_hash,
        },
    )
    return digest


def latest_incident_package_for_session(db: Session, session_id: str) -> models.ForensicPackage | None:
    return db.query(models.ForensicPackage).filter(
        models.ForensicPackage.session_id == session_id,
    ).order_by(models.ForensicPackage.id.desc()).first()


def unresolved_alert_for_session(db: Session, session: models.WardSession) -> models.Alert | None:
    return db.query(models.Alert).filter(
        models.Alert.device_id == session.device_id,
        models.Alert.session_id == session.session_id,
        models.Alert.is_resolved.is_(False),
    ).order_by(models.Alert.id.desc()).first()


def restore_active_pairings(db: Session) -> None:
    ACTIVE_PAIRINGS_CACHE.clear()
    active_pairings = (
        db.query(models.Pairing)
        .filter(models.Pairing.is_active.is_(True))
        .all()
    )
    for pairing in active_pairings:
        ACTIVE_PAIRINGS_CACHE[pairing.device_id] = {
            "patient_token": pairing.patient_token,
            "bed_no": pairing.bed_no,
            "paired_at": pairing.paired_at.isoformat(),
            "session_id": (
                active_session_for_device(db, pairing.device_id).session_id
                if active_session_for_device(db, pairing.device_id)
                else None
            ),
        }


def seed_data() -> None:
    db = SessionLocal()
    try:
        if not settings.seed_data:
            restore_active_pairings(db)
            return
        if db.query(models.Patient).count() == 0:
            db.add_all(
                [
                    models.Patient(patient_token="ptok-hn-2026-8901-demo",),
                    models.Patient(patient_token="ptok-hn-2026-8902-demo",),
                    models.Patient(patient_token="ptok-hn-2026-8903-demo",),
                ]
            )
            db.add_all(
                [
                    models.Bed(bed_no="W04-B12", ward_id="W04"),
                    models.Bed(bed_no="W04-B13", ward_id="W04"),
                    models.Bed(bed_no="W04-B14", ward_id="W04"),
                ]
            )
            db.add_all(
                [
                    models.Device(device_id="MAC-A1:B2:C3:D4:E5:F6"),
                    models.Device(device_id="MAC-B2:C3:D4:E5:F6:A1"),
                    models.Device(device_id="MAC-C3:D4:E5:F6:A1:B2"),
                ]
            )
            db.commit()
        restore_active_pairings(db)
    finally:
        db.close()


@app.on_event("startup")
def startup_populate() -> None:
    seed_data()


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "system": "IPD Smart Sentinel Hub",
        "environment": settings.environment,
        "schema_management": "startup_create_all" if settings.auto_create_db else "external_migration_required",
        "timestamp": utc_now().isoformat(),
        "active_cached_pairings_count": len(ACTIVE_PAIRINGS_CACHE),
        "device_trust_mode": settings.device_trust_mode,
        "telemetry_store": TELEMETRY_STORE.stats(),
    }


def require_local_kiosk(request: Request) -> dict[str, Any]:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="Kiosk bootstrap is local-only.")
    return {"token_subject": "local-tablet-kiosk", "scopes": ["telemetry:read"]}


@app.get("/kiosk", response_class=HTMLResponse)
def kiosk_page(request: Request) -> HTMLResponse:
    require_local_kiosk(request)
    return HTMLResponse(
        """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Smart Ward Hub</title><style>
:root{font-family:system-ui,sans-serif;color:#eaf2f8;background:#10202b}body{margin:0;padding:24px}header{display:flex;justify-content:space-between;gap:16px;align-items:center}h1{font-size:28px;margin:0}.banner{padding:12px 16px;border-radius:10px;background:#244052;margin:20px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.bed{padding:18px;border-radius:14px;background:#1a3342;border:1px solid #315267}.bed h2{margin:0 0 8px}.state{font-weight:700}.warning{color:#ffd166}.danger{color:#ff6b6b}.ok{color:#7be495}.meta{opacity:.8;font-size:14px}
</style></head><body><header><h1>Smart Ward Hub</h1><div id=\"clock\"></div></header><div id=\"banner\" class=\"banner\">Starting local Edge restore…</div><main id=\"grid\" class=\"grid\"></main><script>
const banner=document.getElementById('banner'),grid=document.getElementById('grid');
function esc(v){const d=document.createElement('div');d.textContent=String(v??'');return d.innerHTML;}
function render(data){banner.textContent=data.reconciliation_required?'RESTORED — RECONCILIATION REQUIRED':'RESTORED — LOCAL MONITORING STATE';banner.className='banner '+(data.reconciliation_required?'warning':'ok');grid.innerHTML=data.sessions.map(s=>`<section class=\"bed\"><h2>${esc(s.bed_no)}</h2><div class=\"state\">${esc(s.session_status)} · ${esc(s.telemetry_state)}</div><div class=\"meta\">Device ${esc(s.device_id)}<br>Trust ${esc(s.trust_state)}<br>Last sequence ${esc(s.last_sequence)}<br>Freshness ${esc(s.freshness_seconds)} seconds</div></section>`).join('')||'<div class=\"banner\">No active sessions restored.</div>';}
async function boot(){try{const r=await fetch('/api/v1/kiosk/local-bootstrap');if(!r.ok)throw new Error('bootstrap '+r.status);const j=await r.json();render(j.data);}catch(e){banner.textContent='EDGE_SERVICE_DEGRADED — manual recovery required';banner.className='banner danger';}}
setInterval(()=>document.getElementById('clock').textContent=new Date().toLocaleString(),1000);boot();setInterval(boot,15000);
</script></body></html>"""
    )


@app.get("/admission", response_class=HTMLResponse)
def outside_admission_page(request: Request) -> HTMLResponse:
    require_local_kiosk(request)
    return HTMLResponse(
        """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Smart Ward Hub — Admission Console</title><style>
:root{font-family:system-ui,sans-serif;color:#12202b;background:#eef3f5}body{max-width:1100px;margin:0 auto;padding:24px}header{display:flex;justify-content:space-between;align-items:center;gap:16px}h1{font-size:26px}.note{padding:12px 16px;background:#fff8d6;border:1px solid #e3c75f;border-radius:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:20px 0}.bed{padding:18px;min-height:80px;border:0;border-radius:14px;background:#d9f5df;color:#123; font-size:17px;text-align:left}.bed:disabled{background:#d9dfe2;color:#61717b}.bed.selected{outline:4px solid #1d75bd}.panel{padding:18px;background:white;border-radius:14px;box-shadow:0 2px 8px #0001}.panel input,.panel button{font-size:17px;padding:12px;border-radius:8px}.panel input{width:min(100%,560px);border:1px solid #9aaab2}.panel button{border:0;background:#1d75bd;color:#fff;margin-top:12px}.status{margin-top:12px;font-weight:700}.muted{color:#5f6f78;font-size:14px}
</style></head><body><header><h1>Smart Ward Hub — Outside Admission</h1><div id=\"clock\"></div></header><p class=\"note\">เลือกเฉพาะเตียงที่ Hub รายงานว่าว่าง แล้วส่ง <b>opaque patient/encounter token</b> จาก Admission Gateway ห้ามกรอก raw HN/AN ในหน้านี้</p><section class=\"panel\"><h2>สถานะเตียง</h2><div id=\"grid\" class=\"grid\"></div><div id=\"selected\" class=\"status\">ยังไม่ได้เลือกเตียง</div></section><section class=\"panel\" style=\"margin-top:18px\"><h2>เตรียมรับผู้ป่วย</h2><form id=\"form\"><label>Opaque patient/encounter token<br><input id=\"token\" minlength=\"16\" maxlength=\"128\" autocomplete=\"off\" required></label><br><button type=\"submit\">เตรียม Admission</button></form><div id=\"result\" class=\"status\"></div><p class=\"muted\">การเตรียมนี้จะจองเตียงชั่วคราวเท่านั้น การจับคู่สายรัดและเริ่ม session ต้องทำใน workflow ที่ได้รับอนุญาต</p></section><script>
let selectedBed=null;const grid=document.getElementById('grid'),selected=document.getElementById('selected'),result=document.getElementById('result');
function selectBed(b){selectedBed=b.bed_no;selected.textContent=`เลือกเตียง ${b.bed_no} · ${b.availability_state}`;Array.from(grid.children).forEach(x=>x.classList.toggle('selected',x.dataset.bed===selectedBed));}
async function loadBeds(){try{const r=await fetch('/api/v1/outside/local-bed-availability');if(!r.ok)throw new Error(r.status);const j=await r.json();grid.replaceChildren();j.data.beds.forEach(b=>{const x=document.createElement('button');x.className='bed';x.dataset.bed=b.bed_no;x.disabled=b.availability_state!=='AVAILABLE';x.textContent=`${b.bed_no} — ${b.availability_state}`;x.onclick=()=>selectBed(b);grid.appendChild(x);});}catch(e){result.textContent='ADMISSION HANDOFF UNAVAILABLE — ตรวจสอบ Fixed Hub';}}
document.getElementById('form').addEventListener('submit',async e=>{e.preventDefault();if(!selectedBed){result.textContent='กรุณาเลือกเตียงที่ว่าง';return;}const token=document.getElementById('token').value.trim();try{const r=await fetch('/api/v1/outside/local-admission-preparations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient_token:token,bed_no:selectedBed,idempotency_key:crypto.randomUUID(),source_console_id:'acer-outside-01'})});const j=await r.json();result.textContent=r.ok?`สำเร็จ: ${j.data.admission_id} · เตียง ${j.data.bed_no} RESERVED`:j.detail||'เตรียม Admission ไม่สำเร็จ';await loadBeds();}catch(e){result.textContent='ADMISSION HANDOFF UNAVAILABLE — ไม่ได้ยืนยันการลงทะเบียน';}});
setInterval(()=>document.getElementById('clock').textContent=new Date().toLocaleString(),1000);loadBeds();setInterval(loadBeds,10000);
</script></body></html>"""
    )


@app.get("/api/v1/kiosk/bootstrap", response_model=schemas.BaseResponse)
def kiosk_bootstrap(
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("telemetry:read")),
) -> schemas.BaseResponse:
    restored_at = utc_now()
    session_rows = db.query(models.WardSession).filter(
        models.WardSession.status.in_(["ACTIVE", "RESET_PENDING", "INCIDENT_FROZEN"]),
    ).order_by(models.WardSession.bed_no.asc()).all()
    restored_sessions: list[dict[str, Any]] = []
    reconciliation_required = False
    for session in session_rows:
        samples = TELEMETRY_STORE.snapshot(session.device_id)
        latest = samples[-1] if samples else None
        last_received = latest.get("received_at") if latest else None
        freshness_seconds = None
        if isinstance(last_received, datetime):
            freshness_seconds = max(0, int((restored_at - last_received).total_seconds()))
        trust_state = "DISABLED"
        credential = _active_device_credential(db, session.device_id)
        if settings.device_trust_mode == "enforce":
            trust_state = "ENROLLED" if credential is not None else "UNENROLLED"
        elif settings.device_trust_mode == "observe":
            trust_state = "OBSERVE"
        telemetry_state = "NO_HEARTBEAT" if latest is None else (
            "STALE" if freshness_seconds is not None and freshness_seconds > 120 else "FRESH"
        )
        needs_reconciliation = (
            telemetry_state in {"NO_HEARTBEAT", "STALE"}
            or trust_state in {"UNENROLLED"}
            or session.status in {"RESET_PENDING", "INCIDENT_FROZEN"}
        )
        reconciliation_required = reconciliation_required or needs_reconciliation
        restored_sessions.append({
            "session_id": session.session_id,
            "bed_no": session.bed_no,
            "device_id": session.device_id,
            "session_status": session.status,
            "last_telemetry_at": last_received.isoformat() if isinstance(last_received, datetime) else None,
            "freshness_seconds": freshness_seconds,
            "last_sequence": TELEMETRY_STORE.last_sequence(session.device_id),
            "telemetry_state": telemetry_state,
            "trust_state": trust_state,
            "battery_pct": latest.get("battery_pct") if latest else None,
            "requires_reconciliation": needs_reconciliation,
        })
    AUDIT_SINK.record(
        "kiosk.bootstrap",
        "success",
        actor=_auth,
        resource_type="kiosk",
        resource_id="tablet-local",
        details={"session_count": len(restored_sessions), "reconciliation_required": reconciliation_required},
    )
    return schemas.BaseResponse(
        success=True,
        message="Latest non-PII ward state restored for kiosk display.",
        data={
            "restored_at": restored_at.isoformat(),
            "restore_state": "RESTORED",
            "edge_service_state": "HEALTHY",
            "device_trust_mode": settings.device_trust_mode,
            "reconciliation_required": reconciliation_required,
            "sessions": restored_sessions,
        },
    )


@app.get("/api/v1/kiosk/local-bootstrap", response_model=schemas.BaseResponse)
def kiosk_local_bootstrap(
    request: Request,
    db: Session = Depends(get_db),
    _local: dict[str, Any] = Depends(require_local_kiosk),
) -> schemas.BaseResponse:
    return kiosk_bootstrap(db=db, _auth=_local)


def _set_bed_state(bed: models.Bed, state: str, now: datetime) -> None:
    if bed.availability_state != state:
        bed.availability_state = state
        bed.availability_revision = (bed.availability_revision or 0) + 1
    bed.availability_updated_at = now


def _expire_admission_preparations(db: Session, now: datetime) -> int:
    expired = db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.status == "PREPARED",
        models.AdmissionPreparation.expires_at <= now,
    ).all()
    changed = 0
    for preparation in expired:
        preparation.status = "EXPIRED"
        preparation.updated_at = now
        bed = db.query(models.Bed).filter(models.Bed.bed_no == preparation.bed_no).first()
        active_pairing = db.query(models.Pairing).filter(
            models.Pairing.bed_no == preparation.bed_no,
            models.Pairing.is_active.is_(True),
        ).first()
        other_preparation = db.query(models.AdmissionPreparation).filter(
            models.AdmissionPreparation.bed_no == preparation.bed_no,
            models.AdmissionPreparation.status == "PREPARED",
            models.AdmissionPreparation.expires_at > now,
            models.AdmissionPreparation.id != preparation.id,
        ).first()
        if bed is not None and active_pairing is None and other_preparation is None:
            _set_bed_state(bed, "AVAILABLE", now)
        changed += 1
    return changed


def _bed_availability_row(db: Session, bed: models.Bed, now: datetime) -> dict[str, Any]:
    active_pairing = db.query(models.Pairing).filter(
        models.Pairing.bed_no == bed.bed_no,
        models.Pairing.is_active.is_(True),
    ).first()
    preparation = db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.bed_no == bed.bed_no,
        models.AdmissionPreparation.status == "PREPARED",
        models.AdmissionPreparation.expires_at > now,
    ).order_by(models.AdmissionPreparation.id.desc()).first()
    if active_pairing is not None:
        effective_state = "OCCUPIED"
    elif preparation is not None:
        effective_state = "RESERVED"
    elif bed.availability_state == "RESERVED":
        _set_bed_state(bed, "AVAILABLE", now)
        effective_state = "AVAILABLE"
    else:
        effective_state = bed.availability_state
    return {
        "bed_no": bed.bed_no,
        "ward_id": bed.ward_id,
        "availability_state": effective_state,
        "availability_revision": bed.availability_revision,
        "availability_updated_at": bed.availability_updated_at.isoformat() if bed.availability_updated_at else None,
        "reservation_expires_at": preparation.expires_at.isoformat() if preparation else None,
    }


@app.get("/api/v1/outside/bed-availability", response_model=schemas.BaseResponse)
def outside_bed_availability(
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("admission:read")),
) -> schemas.BaseResponse:
    now = utc_now()
    _expire_admission_preparations(db, now)
    beds = db.query(models.Bed).order_by(models.Bed.ward_id.asc(), models.Bed.bed_no.asc()).all()
    rows = [_bed_availability_row(db, bed, now) for bed in beds]
    db.commit()
    AUDIT_SINK.record(
        "outside.bed_availability.read",
        "success",
        actor=_auth,
        resource_type="ward_bed_snapshot",
        resource_id="ward",
        details={"bed_count": len(rows)},
    )
    return schemas.BaseResponse(
        success=True,
        message="Authoritative non-PII bed availability snapshot.",
        data={"source": "fixed-edge-hub", "as_of": now.isoformat(), "beds": rows},
    )


@app.get("/api/v1/outside/local-bed-availability", response_model=schemas.BaseResponse)
def outside_local_bed_availability(
    request: Request,
    db: Session = Depends(get_db),
    _local: dict[str, Any] = Depends(require_local_kiosk),
) -> schemas.BaseResponse:
    return outside_bed_availability(db=db, _auth=_local)


@app.post("/api/v1/outside/beds/{bed_no}/state", response_model=schemas.BaseResponse)
def update_outside_bed_state(
    bed_no: str,
    request: schemas.BedAvailabilityStateRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("admission:write")),
) -> schemas.BaseResponse:
    bed = db.query(models.Bed).filter(models.Bed.bed_no == bed_no).first()
    if bed is None:
        raise HTTPException(status_code=404, detail="Bed not found.")
    now = utc_now()
    _expire_admission_preparations(db, now)
    if request.state != "AVAILABLE":
        active_pairing = db.query(models.Pairing).filter(
            models.Pairing.bed_no == bed_no,
            models.Pairing.is_active.is_(True),
        ).first()
        active_preparation = db.query(models.AdmissionPreparation).filter(
            models.AdmissionPreparation.bed_no == bed_no,
            models.AdmissionPreparation.status == "PREPARED",
            models.AdmissionPreparation.expires_at > now,
        ).first()
        if active_pairing is not None or active_preparation is not None:
            raise HTTPException(status_code=409, detail="Cannot change a reserved or occupied bed state.")
    _set_bed_state(bed, request.state, now)
    db.commit()
    AUDIT_SINK.record(
        "outside.bed_state.update",
        "success",
        actor=_auth,
        resource_type="bed",
        resource_id=bed_no,
        details={"state": request.state, "reason": request.reason},
    )
    return schemas.BaseResponse(
        success=True,
        message="Bed availability state updated.",
        data={"bed_no": bed_no, "availability_state": request.state, "availability_revision": bed.availability_revision},
    )


@app.post("/api/v1/outside/admission-preparations", response_model=schemas.BaseResponse)
def prepare_outside_admission(
    request: schemas.AdmissionPreparationRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("admission:write")),
) -> schemas.BaseResponse:
    now = utc_now()
    existing = db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.idempotency_key == request.idempotency_key,
    ).first()
    if existing is not None:
        AUDIT_SINK.record(
            "outside.admission_prepare",
            "idempotent_replay",
            actor=_auth,
            resource_type="admission_preparation",
            resource_id=existing.admission_id,
            details={"bed_no": existing.bed_no, "status": existing.status},
        )
        return schemas.BaseResponse(
            success=True,
            message="Admission preparation already exists; returning authoritative result.",
            data={
                "admission_id": existing.admission_id,
                "bed_no": existing.bed_no,
                "status": existing.status,
                "expires_at": existing.expires_at.isoformat(),
                "committed_session_id": existing.committed_session_id,
            },
        )
    _expire_admission_preparations(db, now)
    patient = db.query(models.Patient).filter(models.Patient.patient_token == request.patient_token).first()
    if patient is None:
        patient = models.Patient(patient_token=request.patient_token)
        db.add(patient)
        db.flush()
    bed = db.query(models.Bed).filter(models.Bed.bed_no == request.bed_no).first()
    if bed is None:
        raise HTTPException(status_code=404, detail="Bed not found.")
    active_pairing = db.query(models.Pairing).filter(
        models.Pairing.bed_no == request.bed_no,
        models.Pairing.is_active.is_(True),
    ).first()
    if active_pairing is not None:
        raise HTTPException(status_code=409, detail="Bed is occupied.")
    active_preparation = db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.bed_no == request.bed_no,
        models.AdmissionPreparation.status == "PREPARED",
        models.AdmissionPreparation.expires_at > now,
    ).first()
    if active_preparation is not None:
        raise HTTPException(status_code=409, detail="Bed is already reserved for admission preparation.")
    if bed.availability_state in {"CLEANING", "BLOCKED", "MAINTENANCE"}:
        raise HTTPException(status_code=409, detail=f"Bed is not available from state {bed.availability_state}.")
    expires_at = now + timedelta(seconds=request.expires_in_seconds)
    preparation = models.AdmissionPreparation(
        admission_id=f"admission-{uuid4().hex}",
        bed_no=request.bed_no,
        patient_token=request.patient_token,
        status="PREPARED",
        idempotency_key=request.idempotency_key,
        source_console_id=request.source_console_id,
        prepared_by=str(_auth.get("token_subject") or _auth.get("sub") or "operator"),
        expires_at=expires_at,
    )
    db.add(preparation)
    _set_bed_state(bed, "RESERVED", now)
    db.commit()
    db.refresh(preparation)
    AUDIT_SINK.record(
        "outside.admission_prepare",
        "success",
        actor=_auth,
        resource_type="admission_preparation",
        resource_id=preparation.admission_id,
        details={"bed_no": request.bed_no, "source_console_id": request.source_console_id, "expires_at": expires_at.isoformat()},
    )
    return schemas.BaseResponse(
        success=True,
        message="Admission prepared outside the ward; physical pairing remains a separate step.",
        data={
            "admission_id": preparation.admission_id,
            "bed_no": preparation.bed_no,
            "status": preparation.status,
            "expires_at": preparation.expires_at.isoformat(),
            "availability_state": "RESERVED",
            "availability_revision": bed.availability_revision,
            "requires_inside_pairing": True,
        },
    )


@app.post("/api/v1/outside/local-admission-preparations", response_model=schemas.BaseResponse)
def prepare_outside_local_admission(
    request: schemas.AdmissionPreparationRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _local: dict[str, Any] = Depends(require_local_kiosk),
) -> schemas.BaseResponse:
    return prepare_outside_admission(request=request, db=db, _auth=_local)


@app.post("/api/v1/outside/admission-preparations/{admission_id}/cancel", response_model=schemas.BaseResponse)
def cancel_outside_admission(
    admission_id: str,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("admission:write")),
) -> schemas.BaseResponse:
    preparation = db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.admission_id == admission_id,
    ).first()
    if preparation is None:
        raise HTTPException(status_code=404, detail="Admission preparation not found.")
    now = utc_now()
    if preparation.status == "PREPARED":
        preparation.status = "CANCELLED"
        preparation.updated_at = now
        bed = db.query(models.Bed).filter(models.Bed.bed_no == preparation.bed_no).first()
        active_pairing = db.query(models.Pairing).filter(
            models.Pairing.bed_no == preparation.bed_no,
            models.Pairing.is_active.is_(True),
        ).first()
        if bed is not None and active_pairing is None:
            _set_bed_state(bed, "AVAILABLE", now)
        db.commit()
    AUDIT_SINK.record(
        "outside.admission_cancel",
        "success",
        actor=_auth,
        resource_type="admission_preparation",
        resource_id=admission_id,
        details={"bed_no": preparation.bed_no, "status": preparation.status},
    )
    return schemas.BaseResponse(
        success=True,
        message="Admission preparation cancelled without changing patient identity data.",
        data={"admission_id": admission_id, "bed_no": preparation.bed_no, "status": preparation.status},
    )


def _roaming_state_revision(db: Session) -> int:
    now = utc_now()
    _expire_admission_preparations(db, now)
    state = {
        "beds": [
            (bed.bed_no, bed.availability_state, bed.availability_revision)
            for bed in db.query(models.Bed).order_by(models.Bed.bed_no.asc()).all()
        ],
        "sessions": [
            (session.session_id, session.bed_no, session.device_id, session.status)
            for session in db.query(models.WardSession).filter(
                models.WardSession.status.in_(["ACTIVE", "RESET_PENDING", "INCIDENT_FROZEN"]),
            ).order_by(models.WardSession.session_id.asc()).all()
        ],
        "alerts": [
            (alert.id, alert.bed_no, alert.alert_level, alert.alert_type, alert.acknowledged, alert.is_resolved)
            for alert in db.query(models.Alert).filter(
                models.Alert.is_resolved.is_(False),
            ).order_by(models.Alert.id.asc()).all()
        ],
        "admissions": [
            (prep.admission_id, prep.bed_no, prep.status, prep.expires_at.isoformat())
            for prep in db.query(models.AdmissionPreparation).filter(
                models.AdmissionPreparation.status == "PREPARED",
                models.AdmissionPreparation.expires_at > now,
            ).order_by(models.AdmissionPreparation.admission_id.asc()).all()
        ],
    }
    serialized = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
    return int(hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:15], 16)


def _roaming_snapshot_payload(db: Session, tablet_id: str, since_revision: int | None) -> dict[str, Any]:
    now = utc_now()
    _expire_admission_preparations(db, now)
    revision = _roaming_state_revision(db)
    if since_revision is not None and since_revision == revision:
        return {
            "tablet_id": tablet_id,
            "source": "fixed-edge-hub",
            "as_of": now.isoformat(),
            "revision": revision,
            "cursor": str(revision),
            "unchanged": True,
            "beds": [],
            "sessions": [],
            "alerts": [],
            "admission_tasks": [],
        }

    beds = db.query(models.Bed).order_by(models.Bed.ward_id.asc(), models.Bed.bed_no.asc()).all()
    bed_rows = [_bed_availability_row(db, bed, now) for bed in beds]
    sessions: list[dict[str, Any]] = []
    active_session_ids = set()
    for session in db.query(models.WardSession).filter(
        models.WardSession.status.in_(["ACTIVE", "RESET_PENDING", "INCIDENT_FROZEN"]),
    ).order_by(models.WardSession.bed_no.asc()).all():
        active_session_ids.add(session.session_id)
        samples = TELEMETRY_STORE.snapshot(session.device_id)
        latest = samples[-1] if samples else None
        received_at = latest.get("received_at") if latest else None
        freshness_seconds = None
        if isinstance(received_at, datetime):
            freshness_seconds = max(0, int((now - received_at).total_seconds()))
        telemetry_state = "NO_HEARTBEAT" if latest is None else (
            "STALE" if freshness_seconds is not None and freshness_seconds > 120 else "FRESH"
        )
        credential = _active_device_credential(db, session.device_id)
        trust_state = "DISABLED"
        if settings.device_trust_mode == "enforce":
            trust_state = "ENROLLED" if credential is not None else "UNENROLLED"
        elif settings.device_trust_mode == "observe":
            trust_state = "OBSERVE"
        session_alerts = db.query(models.Alert).filter(
            models.Alert.session_id == session.session_id,
            models.Alert.is_resolved.is_(False),
        ).all()
        sessions.append({
            "session_id": session.session_id,
            "bed_no": session.bed_no,
            "device_id": session.device_id,
            "session_status": session.status,
            "telemetry_state": telemetry_state,
            "freshness_seconds": freshness_seconds,
            "last_telemetry_at": received_at.isoformat() if isinstance(received_at, datetime) else None,
            "last_sequence": TELEMETRY_STORE.last_sequence(session.device_id),
            "battery_pct": latest.get("battery_pct") if latest else None,
            "trust_state": trust_state,
            "active_alert_count": len(session_alerts),
            "requires_reconciliation": telemetry_state != "FRESH" or session.status != "ACTIVE" or trust_state == "UNENROLLED",
        })

    alerts = []
    for alert in db.query(models.Alert).filter(models.Alert.is_resolved.is_(False)).order_by(models.Alert.id.desc()).all():
        alerts.append({
            "alert_id": alert.id,
            "session_id": alert.session_id,
            "bed_no": alert.bed_no,
            "alert_level": alert.alert_level,
            "alert_type": alert.alert_type,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
            "acknowledged": bool(alert.acknowledged),
            "is_resolved": bool(alert.is_resolved),
        })

    admission_tasks = []
    for preparation in db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.status == "PREPARED",
        models.AdmissionPreparation.expires_at > now,
    ).order_by(models.AdmissionPreparation.created_at.desc()).all():
        admission_tasks.append({
            "admission_id": preparation.admission_id,
            "bed_no": preparation.bed_no,
            "status": preparation.status,
            "expires_at": preparation.expires_at.isoformat(),
        })
    return {
        "tablet_id": tablet_id,
        "source": "fixed-edge-hub",
        "as_of": now.isoformat(),
        "revision": revision,
        "cursor": str(revision),
        "unchanged": False,
        "beds": bed_rows,
        "sessions": sessions,
        "alerts": alerts,
        "admission_tasks": admission_tasks,
    }


@app.get("/api/v1/roaming/snapshot", response_model=schemas.BaseResponse)
def roaming_snapshot(
    tablet_id: str,
    since_revision: int | None = None,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("roaming:read")),
) -> schemas.BaseResponse:
    if not tablet_id.strip() or len(tablet_id) > 64:
        raise HTTPException(status_code=422, detail="tablet_id must be a bounded non-empty identifier.")
    payload = _roaming_snapshot_payload(db, tablet_id.strip(), since_revision)
    db.commit()
    AUDIT_SINK.record(
        "roaming.snapshot.read",
        "success",
        actor=_auth,
        resource_type="roaming_tablet",
        resource_id=tablet_id,
        details={"revision": payload["revision"], "unchanged": payload["unchanged"]},
    )
    return schemas.BaseResponse(
        success=True,
        message="Authoritative non-PII roaming snapshot.",
        data=payload,
    )


def _roaming_actor(auth: dict[str, Any]) -> str:
    return str(auth.get("token_subject") or auth.get("sub") or "operator")


def _roaming_rejected_command(
    db: Session,
    command: models.RoamingCommand,
    error_code: str,
    outcome: dict[str, Any],
    auth: dict[str, Any],
) -> None:
    command.status = "REJECTED"
    command.error_code = error_code
    command.outcome_json = json.dumps(outcome, sort_keys=True, separators=(",", ":"), default=str)
    command.processed_at = utc_now()
    db.commit()
    AUDIT_SINK.record(
        "roaming.command",
        "rejected",
        actor=auth,
        resource_type="roaming_command",
        resource_id=command.command_id,
        details={"command_type": command.command_type, "error_code": error_code, "tablet_id": command.tablet_id},
    )


@app.post("/api/v1/roaming/commands", response_model=schemas.BaseResponse)
def roaming_command(
    request: schemas.RoamingCommandRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("roaming:write")),
) -> schemas.BaseResponse:
    existing = db.query(models.RoamingCommand).filter(
        models.RoamingCommand.idempotency_key == request.idempotency_key,
    ).first()
    if existing is not None:
        outcome = json.loads(existing.outcome_json) if existing.outcome_json else {
            "command_id": existing.command_id,
            "status": existing.status,
            "command_type": existing.command_type,
        }
        outcome["idempotent_replay"] = True
        return schemas.BaseResponse(
            success=existing.status == "COMMITTED",
            message="Returning the authoritative roaming command result.",
            data=outcome,
        )

    now = utc_now()
    _expire_admission_preparations(db, now)
    current_revision = _roaming_state_revision(db)
    actor_id = _roaming_actor(_auth)
    command = models.RoamingCommand(
        command_id=request.command_id,
        idempotency_key=request.idempotency_key,
        command_type=request.command_type,
        actor_id=actor_id,
        tablet_id=request.tablet_id,
        session_id=request.session_id,
        alert_id=request.alert_id,
        admission_id=request.admission_id,
        expected_revision=request.expected_revision,
        status="PENDING",
    )
    db.add(command)
    db.flush()

    if request.expected_revision != current_revision:
        outcome = {
            "command_id": request.command_id,
            "command_type": request.command_type,
            "status": "REJECTED",
            "error_code": "STALE_REVISION",
            "current_revision": current_revision,
            "refresh_required": True,
        }
        _roaming_rejected_command(db, command, "STALE_REVISION", outcome, _auth)
        raise HTTPException(status_code=409, detail=outcome)

    if request.command_type == "NOTE":
        outcome = {
            "command_id": request.command_id,
            "command_type": request.command_type,
            "status": "REJECTED",
            "error_code": "NOTE_REQUIRES_APPROVED_DOCUMENTATION_BOUNDARY",
        }
        _roaming_rejected_command(db, command, "NOTE_REQUIRES_APPROVED_DOCUMENTATION_BOUNDARY", outcome, _auth)
        raise HTTPException(status_code=409, detail=outcome)

    if request.command_type == "ACK_ALERT":
        if request.alert_id is None:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "ALERT_ID_REQUIRED"}
            _roaming_rejected_command(db, command, "ALERT_ID_REQUIRED", outcome, _auth)
            raise HTTPException(status_code=422, detail=outcome)
        alert = db.query(models.Alert).filter(models.Alert.id == request.alert_id).first()
        if alert is None or alert.is_resolved:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "ALERT_NOT_ACTIONABLE"}
            _roaming_rejected_command(db, command, "ALERT_NOT_ACTIONABLE", outcome, _auth)
            raise HTTPException(status_code=409, detail=outcome)
        if request.session_id and alert.session_id != request.session_id:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "SESSION_MISMATCH"}
            _roaming_rejected_command(db, command, "SESSION_MISMATCH", outcome, _auth)
            raise HTTPException(status_code=409, detail=outcome)
        alert.acknowledged = True
        alert.acknowledged_by = actor_id
        alert.acknowledged_at = now
        action_result = {"alert_id": alert.id, "acknowledged": True, "acknowledged_by": actor_id}
    elif request.command_type == "ADMISSION_TASK_ACK":
        if not request.admission_id:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "ADMISSION_ID_REQUIRED"}
            _roaming_rejected_command(db, command, "ADMISSION_ID_REQUIRED", outcome, _auth)
            raise HTTPException(status_code=422, detail=outcome)
        preparation = db.query(models.AdmissionPreparation).filter(
            models.AdmissionPreparation.admission_id == request.admission_id,
        ).first()
        if preparation is None:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "ADMISSION_NOT_FOUND"}
            _roaming_rejected_command(db, command, "ADMISSION_NOT_FOUND", outcome, _auth)
            raise HTTPException(status_code=404, detail=outcome)
        action_result = {"admission_id": preparation.admission_id, "bed_no": preparation.bed_no, "status": preparation.status}
    elif request.command_type == "RESET_REQUEST":
        if not request.session_id:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "SESSION_ID_REQUIRED"}
            _roaming_rejected_command(db, command, "SESSION_ID_REQUIRED", outcome, _auth)
            raise HTTPException(status_code=422, detail=outcome)
        session = db.query(models.WardSession).filter(models.WardSession.session_id == request.session_id).first()
        if session is None:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "SESSION_NOT_FOUND"}
            _roaming_rejected_command(db, command, "SESSION_NOT_FOUND", outcome, _auth)
            raise HTTPException(status_code=404, detail=outcome)
        if session.status == "RESET_PENDING":
            action_result = {"session_id": session.session_id, "status": "RESET_PENDING", "confirmation_required": True}
        elif session.status not in {"ACTIVE", "INCIDENT_FROZEN"}:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "SESSION_NOT_RESETTABLE"}
            _roaming_rejected_command(db, command, "SESSION_NOT_RESETTABLE", outcome, _auth)
            raise HTTPException(status_code=409, detail=outcome)
        elif unresolved_alert_for_session(db, session) is not None and latest_incident_package_for_session(db, session.session_id) is None:
            outcome = {"command_id": request.command_id, "status": "REJECTED", "error_code": "INCIDENT_FREEZE_REQUIRED"}
            _roaming_rejected_command(db, command, "INCIDENT_FREEZE_REQUIRED", outcome, _auth)
            raise HTTPException(status_code=409, detail=outcome)
        else:
            session.status = "RESET_PENDING"
            session.reset_pending_at = now
            action_result = {"session_id": session.session_id, "status": "RESET_PENDING", "confirmation_required": True, "ui_signal": "BEEP_SHORT"}
    elif request.command_type == "RESET_CONFIRM":
        outcome = {
            "command_id": request.command_id,
            "status": "REJECTED",
            "error_code": "LIVE_FIXED_HUB_CONFIRMATION_REQUIRED",
            "message": "Roaming Tablet cannot perform destructive reset confirmation in the initial pilot.",
        }
        _roaming_rejected_command(db, command, "LIVE_FIXED_HUB_CONFIRMATION_REQUIRED", outcome, _auth)
        raise HTTPException(status_code=409, detail=outcome)

    command.status = "COMMITTED"
    command.outcome_json = json.dumps(action_result, sort_keys=True, separators=(",", ":"), default=str)
    command.processed_at = now
    db.commit()
    final_revision = _roaming_state_revision(db)
    outcome = {
        "command_id": request.command_id,
        "command_type": request.command_type,
        "status": "COMMITTED",
        "tablet_id": request.tablet_id,
        "current_revision": final_revision,
        "result": action_result,
    }
    command.outcome_json = json.dumps(outcome, sort_keys=True, separators=(",", ":"), default=str)
    db.commit()
    AUDIT_SINK.record(
        "roaming.command",
        "success",
        actor=_auth,
        resource_type="roaming_command",
        resource_id=request.command_id,
        details={"command_type": request.command_type, "tablet_id": request.tablet_id, "current_revision": final_revision},
    )
    return schemas.BaseResponse(
        success=True,
        message="Roaming command committed by Fixed Hub.",
        data=outcome,
    )


@app.post("/api/v1/nfc/pointers", response_model=schemas.BaseResponse)
def enroll_nfc_pointer(
    request: schemas.NfcPointerEnrollmentRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("device-trust:manage")),
) -> schemas.BaseResponse:
    device = db.query(models.Device).filter(models.Device.device_id == request.device_id).first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device is not registered.")
    if request.key_id is not None:
        credential = db.query(models.DeviceCredential).filter(
            models.DeviceCredential.device_id == request.device_id,
            models.DeviceCredential.key_id == request.key_id,
            models.DeviceCredential.status != "REVOKED",
        ).first()
        if credential is None:
            raise HTTPException(status_code=404, detail="Device key credential not found or revoked.")
    existing = db.query(models.NfcPointer).filter(models.NfcPointer.nfc_uid == request.nfc_uid).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="NFC pointer is already enrolled.")
    pointer = models.NfcPointer(
        nfc_uid=request.nfc_uid,
        device_id=request.device_id,
        key_id=request.key_id,
        status="ACTIVE",
    )
    db.add(pointer)
    db.commit()
    AUDIT_SINK.record(
        "nfc.pointer.enroll",
        "success",
        actor=_auth,
        resource_type="nfc_pointer",
        resource_id=request.nfc_uid,
        details={"device_id": request.device_id, "key_id": request.key_id},
    )
    return schemas.BaseResponse(
        success=True,
        message="NFC pointer enrolled as a device lookup index.",
        data={"nfc_uid": request.nfc_uid, "device_id": request.device_id, "key_id": request.key_id},
    )


@app.post("/api/v1/nfc/resolve", response_model=schemas.BaseResponse)
def resolve_nfc_pointer(
    request: schemas.NfcPointerResolveRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    pointer = db.query(models.NfcPointer).filter(
        models.NfcPointer.nfc_uid == request.nfc_uid,
        models.NfcPointer.status == "ACTIVE",
    ).first()
    if pointer is None:
        raise HTTPException(status_code=404, detail="Active NFC pointer not found.")
    AUDIT_SINK.record(
        "nfc.pointer.resolve",
        "success",
        actor=_auth,
        resource_type="nfc_pointer",
        resource_id=request.nfc_uid,
        details={"device_id": pointer.device_id, "key_id": pointer.key_id},
    )
    return schemas.BaseResponse(
        success=True,
        message="NFC pointer resolved; cryptographic device trust remains required for telemetry.",
        data={"nfc_uid": pointer.nfc_uid, "device_id": pointer.device_id, "key_id": pointer.key_id},
    )


@app.post("/api/v1/sessions/{session_id}/incident-freeze", response_model=schemas.BaseResponse)
def freeze_session_incident(
    session_id: str,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("forensics:write")),
) -> schemas.BaseResponse:
    session = db.query(models.WardSession).filter(models.WardSession.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Ward session not found.")
    existing = latest_incident_package_for_session(db, session_id)
    if existing is not None:
        return schemas.BaseResponse(
            success=True,
            message="Incident forensic package already frozen.",
            data={"session_id": session_id, "forensic_package_id": existing.id, "status": session.status},
        )
    alert = unresolved_alert_for_session(db, session)
    if alert is None:
        raise HTTPException(status_code=409, detail="No unresolved incident alert found for session.")
    cutoff = utc_now() - timedelta(minutes=10)
    samples = [
        sample for sample in TELEMETRY_STORE.snapshot(session.device_id)
        if sample.get("received_at") is None or sample["received_at"] >= cutoff
    ]
    package = freeze_forensic_package(db, alert, samples, session_id=session_id)
    session.status = "INCIDENT_FROZEN"
    db.commit()
    AUDIT_SINK.record(
        "session.incident_freeze",
        "success",
        actor=_auth,
        resource_type="ward_session",
        resource_id=session_id,
        details={"forensic_package_id": package.id, "sample_count": len(samples), "window_seconds": 600},
    )
    return schemas.BaseResponse(
        success=True,
        message="Incident forensic package frozen for the recent session window.",
        data={"session_id": session_id, "forensic_package_id": package.id, "status": session.status, "sample_count": len(samples)},
    )


@app.post("/api/v1/sessions/{session_id}/reset-request", response_model=schemas.BaseResponse)
def request_session_reset(
    session_id: str,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    session = db.query(models.WardSession).filter(models.WardSession.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Ward session not found.")
    if session.status == "RESET_PENDING":
        return schemas.BaseResponse(
            success=True,
            message="Reset is already pending visual confirmation.",
            data={"session_id": session_id, "status": "RESET_PENDING", "confirmation_required": True},
        )
    if session.status not in {"ACTIVE", "INCIDENT_FROZEN"}:
        raise HTTPException(status_code=409, detail=f"Session cannot enter reset pending from {session.status}.")
    incident = latest_incident_package_for_session(db, session_id)
    if unresolved_alert_for_session(db, session) is not None and incident is None:
        raise HTTPException(status_code=409, detail="Incident freeze is required before reset.")
    session.status = "RESET_PENDING"
    session.reset_pending_at = utc_now()
    db.commit()
    AUDIT_SINK.record(
        "session.reset_request",
        "success",
        actor=_auth,
        resource_type="ward_session",
        resource_id=session_id,
        details={"device_id": session.device_id, "confirmation_required": True},
    )
    return schemas.BaseResponse(
        success=True,
        message="Reset pending visual confirmation; monitoring remains state-aware until confirmation.",
        data={"session_id": session_id, "status": "RESET_PENDING", "confirmation_required": True, "ui_signal": "BEEP_SHORT"},
    )


@app.post("/api/v1/sessions/{session_id}/reset-confirm", response_model=schemas.BaseResponse)
def confirm_session_reset(
    session_id: str,
    request: schemas.ResetConfirmRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    session = db.query(models.WardSession).filter(models.WardSession.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Ward session not found.")
    if session.status != "RESET_PENDING":
        raise HTTPException(status_code=409, detail="Session is not awaiting reset confirmation.")
    samples = TELEMETRY_STORE.snapshot(session.device_id)
    digest = create_session_close_digest(db, session, samples)
    pairing = db.query(models.Pairing).filter(
        models.Pairing.device_id == session.device_id,
        models.Pairing.is_active.is_(True),
    ).first()
    now = utc_now()
    if pairing is not None:
        pairing.is_active = False
        pairing.unpaired_at = now
    session.status = "SESSION_CLOSED"
    session.closed_at = now
    bed = db.query(models.Bed).filter(models.Bed.bed_no == session.bed_no).first()
    if bed is not None:
        _set_bed_state(bed, "AVAILABLE", now)
    ACTIVE_PAIRINGS_CACHE.pop(session.device_id, None)
    TELEMETRY_STORE.pop(session.device_id)
    db.commit()
    AUDIT_SINK.record(
        "session.reset_confirm",
        "success",
        actor=_auth,
        resource_type="ward_session",
        resource_id=session_id,
        details={"device_id": session.device_id, "digest_hash": digest.digest_hash, "sample_count": digest.sample_count},
    )
    return schemas.BaseResponse(
        success=True,
        message="Device detached, session closed, and volatile application buffer cleared.",
        data={"session_id": session_id, "status": "READY_FOR_CHARGE", "digest_hash": digest.digest_hash, "sample_count": digest.sample_count},
    )


@app.post("/api/v1/sessions/{session_id}/hot-swap", response_model=schemas.BaseResponse)
def hot_swap_session(
    session_id: str,
    request: schemas.HotSwapRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    session = db.query(models.WardSession).filter(models.WardSession.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Ward session not found.")
    if session.status not in {"ACTIVE", "INCIDENT_FROZEN", "RESET_PENDING"}:
        raise HTTPException(status_code=409, detail="Session is not eligible for hot-swap.")
    new_device = db.query(models.Device).filter(
        models.Device.device_id == request.new_device_id,
        models.Device.is_active.is_(True),
    ).first()
    if new_device is None:
        raise HTTPException(status_code=404, detail="New device is not registered or active.")
    if request.new_device_id == session.device_id:
        raise HTTPException(status_code=409, detail="Hot-swap requires a different device.")
    if settings.device_trust_mode == "enforce":
        credential = _active_device_credential(db, request.new_device_id)
        if credential is None or (request.new_key_id and credential.key_id != request.new_key_id):
            raise HTTPException(status_code=409, detail="New device has no matching active Device Trust credential.")
    occupied = db.query(models.Pairing).filter(
        models.Pairing.device_id == request.new_device_id,
        models.Pairing.is_active.is_(True),
    ).first()
    if occupied is not None:
        raise HTTPException(status_code=409, detail="New device is already actively paired.")
    samples = TELEMETRY_STORE.snapshot(session.device_id)
    digest = create_session_close_digest(db, session, samples)
    now = utc_now()
    old_pairing = db.query(models.Pairing).filter(
        models.Pairing.device_id == session.device_id,
        models.Pairing.is_active.is_(True),
    ).first()
    if old_pairing is not None:
        old_pairing.is_active = False
        old_pairing.unpaired_at = now
    session.status = "SESSION_CLOSED"
    session.handover_id = request.handover_id
    session.closed_at = now
    new_pairing = models.Pairing(
        patient_token=session.patient_token,
        bed_no=session.bed_no,
        device_id=request.new_device_id,
        is_active=True,
        paired_at=now,
    )
    new_session = models.WardSession(
        session_id=f"session-{uuid4().hex}",
        device_id=request.new_device_id,
        patient_token=session.patient_token,
        bed_no=session.bed_no,
        handover_id=request.handover_id,
        status="ACTIVE",
    )
    db.add_all([new_pairing, new_session])
    ACTIVE_PAIRINGS_CACHE.pop(session.device_id, None)
    TELEMETRY_STORE.pop(session.device_id)
    db.commit()
    ACTIVE_PAIRINGS_CACHE[request.new_device_id] = {
        "patient_token": session.patient_token,
        "bed_no": session.bed_no,
        "risk_level": "Low",
        "paired_at": now.isoformat(),
        "session_id": new_session.session_id,
    }
    TELEMETRY_STORE.ensure(request.new_device_id)
    AUDIT_SINK.record(
        "session.hot_swap",
        "success",
        actor=_auth,
        resource_type="ward_session",
        resource_id=session_id,
        details={"old_device_id": session.device_id, "new_device_id": request.new_device_id, "handover_id": request.handover_id, "digest_hash": digest.digest_hash, "new_session_id": new_session.session_id},
    )
    return schemas.BaseResponse(
        success=True,
        message="Hot-swap completed with a new session and linked handover ID.",
        data={"old_session_id": session_id, "new_session_id": new_session.session_id, "handover_id": request.handover_id, "digest_hash": digest.digest_hash, "status": "ACTIVE"},
    )


@app.post("/api/v1/sessions/{session_id}/discharge", response_model=schemas.BaseResponse)
def discharge_session(
    session_id: str,
    request: schemas.DischargeRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    session = db.query(models.WardSession).filter(models.WardSession.session_id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Ward session not found.")
    if session.status not in {"ACTIVE", "INCIDENT_FROZEN", "RESET_PENDING"}:
        raise HTTPException(status_code=409, detail="Session is already closed or not dischargeable.")
    incident = latest_incident_package_for_session(db, session_id)
    if unresolved_alert_for_session(db, session) is not None and incident is None:
        raise HTTPException(status_code=409, detail="Incident freeze is required before discharge.")
    digest = create_session_close_digest(db, session, TELEMETRY_STORE.snapshot(session.device_id))
    now = utc_now()
    pairing = db.query(models.Pairing).filter(
        models.Pairing.device_id == session.device_id,
        models.Pairing.is_active.is_(True),
    ).first()
    if pairing is not None:
        pairing.is_active = False
        pairing.unpaired_at = now
    session.status = "SESSION_CLOSED"
    session.handover_id = request.handover_id
    session.closed_at = now
    bed = db.query(models.Bed).filter(models.Bed.bed_no == session.bed_no).first()
    if bed is not None:
        _set_bed_state(bed, "AVAILABLE", now)
    ACTIVE_PAIRINGS_CACHE.pop(session.device_id, None)
    TELEMETRY_STORE.pop(session.device_id)
    db.commit()
    AUDIT_SINK.record(
        "session.discharge",
        "success",
        actor=_auth,
        resource_type="ward_session",
        resource_id=session_id,
        details={"device_id": session.device_id, "handover_id": request.handover_id, "digest_hash": digest.digest_hash},
    )
    return schemas.BaseResponse(
        success=True,
        message="Session discharged and device is ready for charge.",
        data={"session_id": session_id, "handover_id": request.handover_id, "status": "READY_FOR_CHARGE", "digest_hash": digest.digest_hash},
    )


@app.post("/api/v1/device-trust/enroll", response_model=schemas.BaseResponse)
def enroll_device_trust(
    request: schemas.DeviceTrustEnrollmentRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("device-trust:manage")),
) -> schemas.BaseResponse:
    device = db.query(models.Device).filter(models.Device.device_id == request.device_id).first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device is not registered.")
    try:
        fingerprint = public_key_fingerprint(request.public_key_b64)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid Ed25519 public key.") from exc
    existing = db.query(models.DeviceCredential).filter(
        models.DeviceCredential.key_id == request.key_id,
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Device key_id already enrolled.")
    db.query(models.DeviceCredential).filter(
        models.DeviceCredential.device_id == request.device_id,
        models.DeviceCredential.status == "ACTIVE",
    ).update({models.DeviceCredential.status: "SUSPENDED"}, synchronize_session=False)
    credential = models.DeviceCredential(
        device_id=request.device_id,
        key_id=request.key_id,
        algorithm=request.algorithm,
        public_key_b64=request.public_key_b64,
        certificate_fingerprint=request.certificate_fingerprint or fingerprint,
        status="ACTIVE",
        expires_at=normalize_timestamp(request.expires_at) if request.expires_at else None,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    AUDIT_SINK.record(
        "device_trust.enroll",
        "success",
        actor=_auth,
        resource_type="device_credential",
        resource_id=request.key_id,
        details={"device_id": request.device_id, "algorithm": request.algorithm, "fingerprint": fingerprint},
    )
    return schemas.BaseResponse(
        success=True,
        message="Device public-key credential enrolled.",
        data={
            "device_id": request.device_id,
            "key_id": request.key_id,
            "algorithm": request.algorithm,
            "status": credential.status,
            "fingerprint": fingerprint,
        },
    )


@app.post("/api/v1/device-trust/{device_id}/lifecycle", response_model=schemas.BaseResponse)
def update_device_trust_lifecycle(
    device_id: str,
    request: schemas.DeviceTrustLifecycleRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("device-trust:manage")),
) -> schemas.BaseResponse:
    credential = db.query(models.DeviceCredential).filter(
        models.DeviceCredential.device_id == device_id,
        models.DeviceCredential.key_id == request.key_id,
    ).first()
    if credential is None:
        raise HTTPException(status_code=404, detail="Device credential not found.")
    if credential.status == "REVOKED" and request.status == "ACTIVE":
        raise HTTPException(status_code=409, detail="Revoked credentials cannot be reactivated.")
    credential.status = request.status
    credential.revoked_at = utc_now() if request.status == "REVOKED" else None
    db.commit()
    AUDIT_SINK.record(
        "device_trust.lifecycle",
        "success",
        actor=_auth,
        resource_type="device_credential",
        resource_id=request.key_id,
        details={"device_id": device_id, "status": request.status},
    )
    return schemas.BaseResponse(
        success=True,
        message=f"Device credential status changed to {request.status}.",
        data={"device_id": device_id, "key_id": request.key_id, "status": request.status},
    )


@app.post("/api/v1/pairing", response_model=schemas.BaseResponse)
def admissions_and_pairing(
    request: schemas.PairingRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    patient = db.query(models.Patient).filter(models.Patient.patient_token == request.patient_token).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {request.patient_token} not found.")

    bed = db.query(models.Bed).filter(models.Bed.bed_no == request.bed_no).first()
    if not bed:
        raise HTTPException(status_code=404, detail=f"Bed {request.bed_no} not found.")

    device = db.query(models.Device).filter(models.Device.device_id == request.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {request.device_id} not registered.")
    if not device.is_active:
        raise HTTPException(status_code=409, detail=f"Device {request.device_id} is inactive.")
    if settings.device_trust_mode == "enforce" and _active_device_credential(db, request.device_id) is None:
        raise HTTPException(status_code=409, detail="Device Trust enrollment is required before pairing.")

    now = utc_now()
    admission_preparation = db.query(models.AdmissionPreparation).filter(
        models.AdmissionPreparation.bed_no == request.bed_no,
        models.AdmissionPreparation.patient_token == request.patient_token,
        models.AdmissionPreparation.status == "PREPARED",
        models.AdmissionPreparation.expires_at > now,
    ).order_by(models.AdmissionPreparation.id.desc()).first()

    try:
        active_pairings = db.query(models.Pairing).filter(
            models.Pairing.is_active.is_(True),
            (models.Pairing.bed_no == request.bed_no)
            | (models.Pairing.device_id == request.device_id),
        ).all()
        for pairing in active_pairings:
            pairing.is_active = False
            pairing.unpaired_at = now
            ACTIVE_PAIRINGS_CACHE.pop(pairing.device_id, None)

        new_pairing = models.Pairing(
            patient_token=request.patient_token,
            bed_no=request.bed_no,
            device_id=request.device_id,
            is_active=True,
            paired_at=normalize_timestamp(request.timestamp),
        )
        db.add(new_pairing)
        session_record = models.WardSession(
            session_id=f"session-{uuid4().hex}",
            device_id=request.device_id,
            patient_token=request.patient_token,
            bed_no=request.bed_no,
            status="ACTIVE",
        )
        db.add(session_record)
        if admission_preparation is not None:
            admission_preparation.status = "COMMITTED"
            admission_preparation.committed_session_id = session_record.session_id
            admission_preparation.updated_at = now
        _set_bed_state(bed, "OCCUPIED", now)
        db.commit()
        db.refresh(new_pairing)
        db.refresh(session_record)
    except Exception:
        db.rollback()
        raise

    ACTIVE_PAIRINGS_CACHE[request.device_id] = {
        "patient_token": request.patient_token,
        "bed_no": request.bed_no,
        "risk_level": request.risk_level,
        "paired_at": new_pairing.paired_at.isoformat(),
        "session_id": session_record.session_id,
    }
    TELEMETRY_STORE.ensure(request.device_id)
    AUDIT_SINK.record(
        "pairing.create",
        "success",
        actor=_auth,
        resource_type="pairing",
        resource_id=str(new_pairing.id),
        details={
            "device_id": request.device_id,
            "bed_no": request.bed_no,
            "patient_token": request.patient_token,
            "session_id": session_record.session_id,
        },
    )

    return schemas.BaseResponse(
        success=True,
        message=f"Successfully paired Patient {request.patient_token} with Bed {request.bed_no}.",
        data={
            "pairing_id": new_pairing.id,
            "bed_no": request.bed_no,
            "device_id": request.device_id,
            "paired_at": new_pairing.paired_at.isoformat(),
            "session_id": session_record.session_id,
            "admission_id": admission_preparation.admission_id if admission_preparation else None,
            "admission_status": admission_preparation.status if admission_preparation else None,
            "visual_feedback": "LED Flash Green x2",
        },
    )


@app.post("/api/v1/unpair", response_model=schemas.BaseResponse)
def unbind_and_discharge(
    request: schemas.UnbindRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("pairing:write")),
) -> schemas.BaseResponse:
    pairing = db.query(models.Pairing).filter(
        models.Pairing.device_id == request.device_id,
        models.Pairing.is_active.is_(True),
    ).first()
    if not pairing:
        raise HTTPException(status_code=400, detail="No active pairing found for device.")

    session = active_session_for_device(db, request.device_id)
    if session is not None:
        incident = latest_incident_package_for_session(db, session.session_id)
        if unresolved_alert_for_session(db, session) is not None and incident is None:
            raise HTTPException(status_code=409, detail="Incident freeze is required before unpair/reset.")
        create_session_close_digest(db, session, TELEMETRY_STORE.snapshot(request.device_id))
        session.status = "SESSION_CLOSED"
        session.closed_at = normalize_timestamp(request.timestamp)
    pairing.is_active = False
    pairing.unpaired_at = normalize_timestamp(request.timestamp)
    bed = db.query(models.Bed).filter(models.Bed.bed_no == pairing.bed_no).first()
    if bed is not None:
        _set_bed_state(bed, "AVAILABLE", normalize_timestamp(request.timestamp))
    db.commit()
    ACTIVE_PAIRINGS_CACHE.pop(request.device_id, None)
    TELEMETRY_STORE.pop(request.device_id)
    AUDIT_SINK.record(
        "pairing.remove",
        "success",
        actor=_auth,
        resource_type="pairing",
        resource_id=str(pairing.id),
        details={"device_id": request.device_id, "patient_token": pairing.patient_token, "session_id": session.session_id if session else None},
    )

    return schemas.BaseResponse(
        success=True,
        message=f"Device {request.device_id} successfully unbound.",
        data={
            "pairing_id": pairing.id,
            "unpaired_at": pairing.unpaired_at.isoformat(),
            "charging_status": "Connected to Central Dock",
        },
    )


@app.post("/api/v1/telemetry", response_model=schemas.BaseResponse)
def ingest_telemetry(
    packet: schemas.TelemetryPacket,
    http_request: Request,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("telemetry:write")),
) -> schemas.BaseResponse:
    """Accept a raw packet only from a currently paired device."""
    device_trust_status = verify_ingress_device_trust(packet, http_request, db)
    binding = ACTIVE_PAIRINGS_CACHE.get(packet.device_id)
    if binding is None:
        raise HTTPException(status_code=403, detail="Device is not actively paired.")

    sample = {
        "sequence": packet.sequence,
        "timestamp": normalize_timestamp(packet.timestamp),
        "received_at": utc_now(),
        "ppg": packet.ppg,
        "accel_x": packet.accel_x,
        "accel_y": packet.accel_y,
        "accel_z": packet.accel_z,
        "g_force": math.sqrt(packet.accel_x ** 2 + packet.accel_y ** 2 + packet.accel_z ** 2),
        "skin_temp": packet.skin_temp,
        "heart_rate": packet.heart_rate,
        "spo2": packet.spo2,
        "battery_pct": packet.battery_pct,
    }
    append_result = TELEMETRY_STORE.append(packet.device_id, sample, packet.sequence)
    if not append_result.accepted:
        AUDIT_SINK.record(
            "telemetry.ingest",
            "replay_rejected",
            actor=_auth,
            resource_type="device",
            resource_id=packet.device_id,
            details={"sequence": packet.sequence, "reason": append_result.reason},
        )
        raise HTTPException(status_code=409, detail=append_result.reason)
    buffer = TELEMETRY_STORE.snapshot(packet.device_id)
    alert = evaluate_triage(packet.device_id, buffer)
    if alert is not None:
        existing = db.query(models.Alert).filter(
            models.Alert.device_id == packet.device_id,
            models.Alert.alert_type == alert["alert_type"],
            models.Alert.is_resolved.is_(False),
        ).first()
        if existing is None:
            alert_record = models.Alert(
                device_id=packet.device_id,
                session_id=binding.get("session_id"),
                bed_no=binding["bed_no"],
                patient_token=binding["patient_token"],
                alert_level=alert["alert_level"],
                alert_type=alert["alert_type"],
                description=alert["description"],
            )
            db.add(alert_record)
            db.commit()
            db.refresh(alert_record)
            freeze_forensic_package(
                db,
                alert_record,
                list(buffer),
                session_id=binding.get("session_id"),
            )
    AUDIT_SINK.record(
        "telemetry.ingest",
        "success",
        actor=_auth,
        resource_type="device",
        resource_id=packet.device_id,
        details={"sequence": packet.sequence, "buffered_samples": append_result.buffered_samples},
    )
    return schemas.BaseResponse(
        success=True,
        message="Telemetry accepted into the in-memory ring buffer.",
        data={
            "device_id": packet.device_id,
            "sequence": packet.sequence,
            "buffered_samples": append_result.buffered_samples,
            "dropped_samples": append_result.dropped_samples,
            "device_trust": device_trust_status,
        },
    )


@app.post(
    "/api/v1/telemetry/aggregate/{device_id}",
    response_model=schemas.TelemetryAggregateResponse,
)
def aggregate_telemetry(
    device_id: str,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("telemetry:read")),
):
    """Summarize a device buffer into SQLite, then purge the RAM buffer."""
    binding = ACTIVE_PAIRINGS_CACHE.get(device_id)
    buffer = TELEMETRY_STORE.snapshot(device_id)
    if binding is None:
        raise HTTPException(status_code=403, detail="Device is not actively paired.")
    if not buffer:
        raise HTTPException(status_code=404, detail="No telemetry samples available.")

    samples = list(buffer)
    ppg_values = [sample["ppg"] for sample in samples]
    temp_values = [sample["skin_temp"] for sample in samples]
    heart_rate_values = [sample["heart_rate"] for sample in samples if sample.get("heart_rate") is not None]
    spo2_values = [sample["spo2"] for sample in samples if sample.get("spo2") is not None]
    accel_values = [
        math.sqrt(sample["accel_x"] ** 2 + sample["accel_y"] ** 2 + sample["accel_z"] ** 2)
        for sample in samples
    ]
    aggregate = models.TelemetryAggregate(
        device_id=device_id,
        patient_token=binding["patient_token"],
        bed_no=binding["bed_no"],
        sample_count=len(samples),
        ppg_avg=round(sum(ppg_values) / len(ppg_values), 3),
        ppg_min=min(ppg_values),
        ppg_max=max(ppg_values),
        heart_rate_avg=round(sum(heart_rate_values) / len(heart_rate_values), 3) if heart_rate_values else None,
        heart_rate_min=min(heart_rate_values) if heart_rate_values else None,
        heart_rate_max=max(heart_rate_values) if heart_rate_values else None,
        spo2_avg=round(sum(spo2_values) / len(spo2_values), 3) if spo2_values else None,
        spo2_min=min(spo2_values) if spo2_values else None,
        spo2_max=max(spo2_values) if spo2_values else None,
        skin_temp_avg=round(sum(temp_values) / len(temp_values), 3),
        skin_temp_min=min(temp_values),
        skin_temp_max=max(temp_values),
        battery_latest=samples[-1]["battery_pct"],
        max_accel_g=round(max(accel_values), 3),
        window_start=min(sample["timestamp"] for sample in samples),
        window_end=max(sample["timestamp"] for sample in samples),
    )
    db.add(aggregate)
    db.commit()
    db.refresh(aggregate)
    TELEMETRY_STORE.clear_device(device_id)
    AUDIT_SINK.record(
        "telemetry.aggregate",
        "success",
        actor=_auth,
        resource_type="device",
        resource_id=device_id,
        details={"sample_count": aggregate.sample_count, "patient_token": aggregate.patient_token},
    )

    return schemas.TelemetryAggregateResponse(
        device_id=aggregate.device_id,
        patient_token=aggregate.patient_token,
        bed_no=aggregate.bed_no,
        sample_count=aggregate.sample_count,
        ppg_avg=aggregate.ppg_avg,
        ppg_min=aggregate.ppg_min,
        ppg_max=aggregate.ppg_max,
        heart_rate_avg=aggregate.heart_rate_avg,
        heart_rate_min=aggregate.heart_rate_min,
        heart_rate_max=aggregate.heart_rate_max,
        spo2_avg=aggregate.spo2_avg,
        spo2_min=aggregate.spo2_min,
        spo2_max=aggregate.spo2_max,
        skin_temp_avg=aggregate.skin_temp_avg,
        skin_temp_min=aggregate.skin_temp_min,
        skin_temp_max=aggregate.skin_temp_max,
        battery_latest=aggregate.battery_latest,
        max_accel_g=aggregate.max_accel_g,
        window_start=aggregate.window_start.isoformat(),
        window_end=aggregate.window_end.isoformat(),
    )



def evaluate_triage(device_id: str, samples: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return a prototype alert when a fall or physiological anomaly is detected."""
    binding = ACTIVE_PAIRINGS_CACHE.get(device_id)
    if binding is None:
        return None

    recent = samples[-30:]
    for index, sample in enumerate(recent):
        if sample["g_force"] <= 2.5:
            continue
        subsequent = recent[index + 1 : index + 6]
        if len(subsequent) < 5:
            continue
        g_forces = [item["g_force"] for item in subsequent]
        if pstdev(g_forces) < 0.15 and abs(sum(g_forces) / len(g_forces) - 1.0) < 0.25:
            return {
                "alert_level": "RED",
                "alert_type": "FALL",
                "description": f"Silent fall pattern detected at bed {binding['bed_no']}.",
            }

    latest = recent[-1]
    physiological_score = 0.0
    if latest.get("spo2") is not None:
        if latest["spo2"] < 90:
            physiological_score += 100
        elif latest["spo2"] < 95:
            physiological_score += 40
    if latest.get("heart_rate") is not None and (
        latest["heart_rate"] < 50 or latest["heart_rate"] > 120
    ):
        physiological_score += 60
    risk_score = {"High": 100.0, "Medium": 50.0, "Low": 10.0}.get(
        binding.get("risk_level", "Low"),
        10.0,
    )
    triage_score = (0.618 * min(100.0, physiological_score)) + (0.382 * risk_score)
    if triage_score >= 50.0 or (latest.get("spo2") is not None and latest["spo2"] < 90):
        return {
            "alert_level": "RED",
            "alert_type": "VITAL_ANOMALY",
            "description": f"Vital anomaly triage score {triage_score:.1f}% at bed {binding['bed_no']}.",
        }
    return None


GENESIS_HASH = "0" * 64


def freeze_forensic_package(
    db: Session,
    alert: models.Alert,
    samples: list[dict[str, Any]],
    session_id: str | None = None,
) -> models.ForensicPackage:
    payload = {
        "alert_id": alert.id,
        "session_id": session_id,
        "device_id": alert.device_id,
        "patient_token": alert.patient_token,
        "bed_no": alert.bed_no,
        "alert_level": alert.alert_level,
        "alert_type": alert.alert_type,
        "description": alert.description,
        "samples": samples,
    }
    frozen_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    previous = db.query(models.ForensicPackage).order_by(models.ForensicPackage.id.desc()).first()
    previous_hash = previous.block_hash if previous else GENESIS_HASH
    block_hash = hashlib.sha256(f"{previous_hash}:{frozen_payload}".encode("utf-8")).hexdigest()
    package = models.ForensicPackage(
        alert_id=alert.id,
        session_id=session_id,
        device_id=alert.device_id,
        patient_token=alert.patient_token,
        bed_no=alert.bed_no,
        frozen_payload_json=frozen_payload,
        previous_hash=previous_hash,
        block_hash=block_hash,
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    anchored = ANCHOR_STORE.anchor(
        block_hash=package.block_hash,
        chain_tip=package.block_hash,
        package_id=package.id,
    )
    AUDIT_SINK.record(
        "forensics.freeze",
        "anchored" if anchored else "local_only",
        resource_type="forensic_package",
        resource_id=str(package.id),
        details={"block_hash": package.block_hash, "anchor_configured": anchored},
    )
    return package


@app.get("/api/v1/forensics/verify")
def verify_forensic_chain(
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("forensics:read")),
) -> dict[str, Any]:
    packages = db.query(models.ForensicPackage).order_by(models.ForensicPackage.id.asc()).all()
    previous_hash = GENESIS_HASH
    for package in packages:
        expected_hash = hashlib.sha256(
            f"{previous_hash}:{package.frozen_payload_json}".encode("utf-8")
        ).hexdigest()
        if package.previous_hash != previous_hash or package.block_hash != expected_hash:
            AUDIT_SINK.record(
                "forensics.verify",
                "failed",
                actor=_auth,
                resource_type="forensic_package",
                resource_id=str(package.id),
                details={"package_count": len(packages)},
            )
            return {
                "integrity": "FAILED",
                "tampered_package_id": package.id,
                "detail": "Forensic hash chain verification failed.",
            }
        previous_hash = package.block_hash
    AUDIT_SINK.record(
        "forensics.verify",
        "success",
        actor=_auth,
        resource_type="forensic_chain",
        resource_id="chain",
        details={"package_count": len(packages), "last_hash": previous_hash},
    )
    return {
        "integrity": "OK",
        "package_count": len(packages),
        "last_hash": previous_hash if packages else GENESIS_HASH,
    }



def _metric_summary(rows: list[models.TelemetryAggregate], prefix: str) -> dict[str, float] | None:
    values = [getattr(row, f"{prefix}_{suffix}") for row in rows for suffix in ("avg",) if getattr(row, f"{prefix}_{suffix}") is not None]
    if not values:
        return None
    return {
        "avg": round(sum(values) / len(values), 3),
        "min": min(getattr(row, f"{prefix}_min") for row in rows if getattr(row, f"{prefix}_min") is not None),
        "max": max(getattr(row, f"{prefix}_max") for row in rows if getattr(row, f"{prefix}_max") is not None),
    }


def build_fhir_bundle(
    bundle_id: str,
    patient_token: str,
    metrics: dict[str, Any],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    effective_period = {
        "start": f"{start_time.isoformat()}Z",
        "end": f"{end_time.isoformat()}Z",
    }
    code_map = {
        "heart_rate": ("8867-4", "Heart rate", "beats/minute"),
        "spo2": ("2708-6", "Oxygen saturation in Arterial blood", "%"),
        "skin_temp": ("8310-5", "Body temperature", "Cel"),
    }
    entries = []
    for metric_name, (code, display, unit) in code_map.items():
        metric = metrics.get(metric_name)
        if metric is None:
            continue
        entries.append(
            {
                "fullUrl": f"urn:uuid:observation-{metric_name}-{bundle_id}",
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": code,
                                "display": display,
                            }
                        ]
                    },
                    "subject": {"reference": f"Patient/{patient_token}"},
                    "effectivePeriod": effective_period,
                    "valueQuantity": {
                        "value": metric["avg"],
                        "unit": unit,
                    },
                },
            }
        )
    peak_impact = metrics.get("peak_impact_g")
    if peak_impact is not None:
        entries.append(
            {
                "fullUrl": f"urn:uuid:observation-impact-{bundle_id}",
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": "Peak acceleration magnitude"},
                    "subject": {"reference": f"Patient/{patient_token}"},
                    "effectivePeriod": effective_period,
                    "valueQuantity": {"value": peak_impact, "unit": "g"},
                },
            }
        )
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "timestamp": f"{utc_now().isoformat()}Z",
        "entry": entries,
    }


@app.post("/api/v1/handover/{device_id}", response_model=schemas.HandoverResponse)
def create_handover(
    device_id: str,
    request: schemas.HandoverRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("handover:read")),
):
    binding = ACTIVE_PAIRINGS_CACHE.get(device_id)
    if binding is None:
        raise HTTPException(status_code=403, detail="Device is not actively paired.")
    start_time = normalize_timestamp(request.start_time)
    end_time = normalize_timestamp(request.end_time)
    aggregates = db.query(models.TelemetryAggregate).filter(
        models.TelemetryAggregate.device_id == device_id,
        models.TelemetryAggregate.window_start >= start_time,
        models.TelemetryAggregate.window_end <= end_time,
    ).order_by(models.TelemetryAggregate.window_start.asc()).all()
    if not aggregates:
        raise HTTPException(status_code=404, detail="No aggregates found in handover window.")

    metric_groups = {
        "heart_rate": _metric_summary(aggregates, "heart_rate"),
        "spo2": _metric_summary(aggregates, "spo2"),
        "skin_temp": _metric_summary(aggregates, "skin_temp"),
    }
    metric_groups = {key: value for key, value in metric_groups.items() if value is not None}
    metric_groups["peak_impact_g"] = round(max(row.max_accel_g for row in aggregates), 3)
    alert_count = db.query(models.Alert).filter(
        models.Alert.device_id == device_id,
        models.Alert.timestamp >= start_time,
        models.Alert.timestamp <= end_time,
    ).count()
    bundle_id = f"bundle-shift-handover-{device_id}-{uuid4().hex}"
    fhir_bundle = build_fhir_bundle(
        bundle_id,
        binding["patient_token"],
        metric_groups,
        start_time,
        end_time,
    )
    db.add(models.HandoverRecord(
        device_id=device_id,
        patient_token=binding["patient_token"],
        bed_no=binding["bed_no"],
        start_time=start_time,
        end_time=end_time,
        bundle_id=bundle_id,
        synced=False,
    ))
    db.commit()
    AUDIT_SINK.record(
        "handover.create",
        "success",
        actor=_auth,
        resource_type="handover",
        resource_id=bundle_id,
        details={"device_id": device_id, "aggregate_count": len(aggregates)},
    )
    return schemas.HandoverResponse(
        bundle_id=bundle_id,
        device_id=device_id,
        patient_token=binding["patient_token"],
        bed_no=binding["bed_no"],
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        clinical_metrics=metric_groups,
        alert_count=alert_count,
        fhir_bundle=fhir_bundle,
        sync_status="NOT_SYNCED",
        aggregate_count=len(aggregates),
    )


@app.post("/api/v1/handover/{device_id}/sync/{bundle_id}", response_model=schemas.BaseResponse)
def acknowledge_handover_sync(
    device_id: str,
    bundle_id: str,
    request: schemas.HandoverSyncRequest,
    db: Session = Depends(get_db),
    _auth: dict[str, Any] = Depends(require_scope("handover:sync")),
) -> schemas.BaseResponse:
    with HANDOVER_SYNC_LOCK:
        record = db.query(models.HandoverRecord).filter(
            models.HandoverRecord.device_id == device_id,
            models.HandoverRecord.bundle_id == bundle_id,
        ).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Handover bundle not found.")

        is_acknowledged = request.acknowledged and request.status_code == 200
        if is_acknowledged and request.acknowledged_bundle_id != bundle_id:
            raise HTTPException(
                status_code=409,
                detail="Acknowledgment bundle identity does not match the requested handover.",
            )
        if is_acknowledged and record.synced:
            attempt = models.SyncAttempt(
                device_id=device_id,
                bundle_id=bundle_id,
                status_code=request.status_code,
                acknowledged=True,
                error_message=request.error_message,
            )
            db.add(attempt)
            db.commit()
            AUDIT_SINK.record(
                "handover.sync",
                "idempotent_replay",
                actor=_auth,
                resource_type="handover",
                resource_id=bundle_id,
                details={
                    "status_code": request.status_code,
                    "purged_aggregate_count": record.purged_aggregate_count,
                    "acknowledgment_id": request.acknowledgment_id,
                    "receiving_system": request.receiving_system,
                    "accepted_version": request.accepted_version,
                    "accepted_profile": request.accepted_profile,
                },
            )
            return schemas.BaseResponse(
                success=True,
                message="Handover was already acknowledged; no additional purge was performed.",
                data={
                    "bundle_id": bundle_id,
                    "status_code": request.status_code,
                    "purged_aggregate_count": record.purged_aggregate_count,
                    "sync_status": "ACKNOWLEDGED_IDEMPOTENT",
                },
            )

        attempt = models.SyncAttempt(
            device_id=device_id,
            bundle_id=bundle_id,
            status_code=request.status_code,
            acknowledged=is_acknowledged,
            error_message=request.error_message,
        )
        db.add(attempt)
        if is_acknowledged:
            purged_count = db.query(models.TelemetryAggregate).filter(
                models.TelemetryAggregate.device_id == device_id,
                models.TelemetryAggregate.window_start >= record.start_time,
                models.TelemetryAggregate.window_end <= record.end_time,
            ).delete(synchronize_session=False)
            record.synced = True
            record.purged_aggregate_count = purged_count
            db.commit()
            AUDIT_SINK.record(
                "handover.sync",
                "success",
                actor=_auth,
                resource_type="handover",
                resource_id=bundle_id,
                details={
                    "status_code": request.status_code,
                    "purged_aggregate_count": purged_count,
                    "acknowledgment_id": request.acknowledgment_id,
                    "receiving_system": request.receiving_system,
                    "accepted_version": request.accepted_version,
                    "accepted_profile": request.accepted_profile,
                },
            )
            return schemas.BaseResponse(
                success=True,
                message="Handover acknowledged by the remote system; local aggregates purged.",
                data={
                    "bundle_id": bundle_id,
                    "status_code": request.status_code,
                    "purged_aggregate_count": purged_count,
                    "sync_status": "ACKNOWLEDGED",
                },
            )

        db.commit()
        AUDIT_SINK.record(
            "handover.sync",
            "retained_for_retry",
            actor=_auth,
            resource_type="handover",
            resource_id=bundle_id,
            details={"status_code": request.status_code},
        )
        return schemas.BaseResponse(
            success=False,
            message="Remote synchronization was not acknowledged; local aggregates were retained.",
            data={
                "bundle_id": bundle_id,
                "status_code": request.status_code,
                "sync_status": "RETAINED_FOR_RETRY",
            },
        )
