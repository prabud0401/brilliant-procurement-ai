from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Department, Product, Vendor
from app.core.policy import Principal, get_current_principal
from app.reference.schemas import (
    DepartmentReferenceResponse,
    ProductReferenceResponse,
    VendorReferenceResponse,
)

router = APIRouter(tags=["reference"])


@router.get("/vendors", response_model=list[VendorReferenceResponse])
def list_vendors(
    search: str | None = Query(None, description="Search by vendor name or TRN"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[VendorReferenceResponse]:
    """Read-only list of vendors accessible to all authenticated roles."""
    query = db.query(Vendor)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((Vendor.name.ilike(term)) | (Vendor.trn.ilike(term)))
    rows = query.order_by(Vendor.name.asc()).all()
    return [VendorReferenceResponse.model_validate(r) for r in rows]


@router.get("/products", response_model=list[ProductReferenceResponse])
def list_products(
    search: str | None = Query(None, description="Search by product code or name"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[ProductReferenceResponse]:
    """Read-only catalogue of products accessible to all authenticated roles."""
    query = db.query(Product)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((Product.code.ilike(term)) | (Product.name.ilike(term)))
    rows = query.order_by(Product.code.asc()).all()
    return [ProductReferenceResponse.model_validate(r) for r in rows]


@router.get("/departments", response_model=list[DepartmentReferenceResponse])
def list_departments(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> list[DepartmentReferenceResponse]:
    """Read-only catalogue of departments accessible to all authenticated roles."""
    rows = db.query(Department).order_by(Department.name.asc()).all()
    return [DepartmentReferenceResponse.model_validate(r) for r in rows]
