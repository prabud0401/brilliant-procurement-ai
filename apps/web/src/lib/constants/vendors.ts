export interface Vendor {
  id: string;
  odoo_id?: number | null;
  name: string;
  trn?: string | null;
  payment_terms_days: number;
  lead_time_days?: number;
  address?: string;
  contact_email?: string;
  contact_phone?: string;
  category?: string;
  notes?: string;
}

export type SeededVendor = Vendor;

export interface Product {
  id: string;
  odoo_id?: number | null;
  code: string;
  name: string;
  uom: string;
}

const _vendorCache: Map<string, Vendor> = new Map();

export function setCachedVendors(vendors: Vendor[]): void {
  for (const v of vendors) {
    _vendorCache.set(v.id.toLowerCase(), v);
  }
}

export function getVendorById(id: string | null | undefined): Vendor | undefined {
  if (!id) return undefined;
  const cached = _vendorCache.get(id.toLowerCase());
  if (cached) return cached;
  // If not yet populated by API, return a stub indicating a vendor is linked
  return {
    id,
    name: "Vendor",
    payment_terms_days: 30,
    trn: "100000000000001",
  };
}

export function getVendorByName(name: string | null | undefined): Vendor | undefined {
  if (!name) return undefined;
  const target = name.trim().toLowerCase();
  for (const v of _vendorCache.values()) {
    if (v.name.toLowerCase() === target) return v;
  }
  return undefined;
}

export async function fetchVendors(search?: string): Promise<Vendor[]> {
  const params = new URLSearchParams();
  if (search && search.trim()) {
    params.append("search", search.trim());
  }
  const queryStr = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`/api/v1/vendors${queryStr}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch vendors (HTTP ${res.status})`);
  }
  const data = (await res.json()) as Vendor[];
  setCachedVendors(data);
  return data;
}

export async function fetchProducts(search?: string): Promise<Product[]> {
  const params = new URLSearchParams();
  if (search && search.trim()) {
    params.append("search", search.trim());
  }
  const queryStr = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`/api/v1/products${queryStr}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch products (HTTP ${res.status})`);
  }
  return res.json();
}
