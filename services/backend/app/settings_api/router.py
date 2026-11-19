from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.policy import Principal, get_current_principal, require
from app.settings_api.schemas import SettingResponse, SettingUpdateRequest
from app.settings_api.service import get_setting, update_setting

router = APIRouter(prefix="/settings", tags=["settings"])


def require_settings_read(principal: Principal = Depends(get_current_principal)) -> Principal:
    allowed_roles = {"buyer", "manager", "admin"}
    if not any(r in allowed_roles for r in principal.roles):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Buyer, Manager or Admin role required to view settings",
        )
    return principal


@router.get("/thresholds", response_model=SettingResponse)
def get_thresholds(
    principal: Principal = Depends(require_settings_read),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = get_setting(db, "thresholds")
    return SettingResponse(**res)


@router.put("/thresholds", response_model=SettingResponse)
def put_thresholds(
    body: SettingUpdateRequest,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = update_setting(db, "thresholds", body.value, principal)
    return SettingResponse(**res)


@router.get("/tolerances", response_model=SettingResponse)
def get_tolerances(
    principal: Principal = Depends(require_settings_read),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = get_setting(db, "tolerances")
    return SettingResponse(**res)


@router.put("/tolerances", response_model=SettingResponse)
def put_tolerances(
    body: SettingUpdateRequest,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = update_setting(db, "tolerances", body.value, principal)
    return SettingResponse(**res)


@router.get("/buyer-policy", response_model=SettingResponse)
def get_buyer_policy(
    principal: Principal = Depends(require_settings_read),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = get_setting(db, "buyer-policy")
    return SettingResponse(**res)


@router.put("/buyer-policy", response_model=SettingResponse)
def put_buyer_policy(
    body: SettingUpdateRequest,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = update_setting(db, "buyer-policy", body.value, principal)
    return SettingResponse(**res)


@router.get("/{key}", response_model=SettingResponse)
def get_any_setting(
    key: str,
    principal: Principal = Depends(require_settings_read),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = get_setting(db, key)
    return SettingResponse(**res)


@router.put("/{key}", response_model=SettingResponse)
def put_any_setting(
    key: str,
    body: SettingUpdateRequest,
    principal: Principal = Depends(require("admin.manage")),
    db: Session = Depends(get_db),
) -> SettingResponse:
    res = update_setting(db, key, body.value, principal)
    return SettingResponse(**res)
