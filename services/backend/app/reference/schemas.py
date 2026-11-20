import uuid

from pydantic import BaseModel, ConfigDict


class VendorReferenceResponse(BaseModel):
    id: uuid.UUID
    odoo_id: int | None = None
    name: str
    trn: str | None = None
    payment_terms_days: int = 30

    model_config = ConfigDict(from_attributes=True)


class ProductReferenceResponse(BaseModel):
    id: uuid.UUID
    odoo_id: int | None = None
    code: str
    name: str
    uom: str = "unit"

    model_config = ConfigDict(from_attributes=True)


class DepartmentReferenceResponse(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)
