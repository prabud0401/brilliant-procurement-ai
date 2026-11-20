export interface SeededVendor {
  id: string;
  odoo_id: number;
  name: string;
  trn: string;
  payment_terms_days: number;
  lead_time_days: number;
  address: string;
  contact_email: string;
  contact_phone: string;
  category: string;
  notes?: string;
}

export const SEEDED_VENDORS: SeededVendor[] = [
  {
    id: "02ccc52b-65a0-5878-807e-419178e7b553",
    odoo_id: 1,
    name: "Falcon Office Supplies LLC",
    trn: "100000000000001",
    payment_terms_days: 30,
    lead_time_days: 3,
    address: "Warehouse 14, Sector M-9, Mussafah Industrial Area, Abu Dhabi, UAE",
    contact_email: "orders@falcon-supplies.fake",
    contact_phone: "+971 2 555 0101",
    category: "Office Supplies",
  },
  {
    id: "5cba38c7-118b-5996-a309-80ce9ddf0b49",
    odoo_id: 2,
    name: "Gulf Line IT Trading",
    trn: "100000000000002",
    payment_terms_days: 30,
    lead_time_days: 5,
    address: "Office 402, Tamouh Tower, Al Reem Island, Abu Dhabi, UAE",
    contact_email: "sales@gulfline-it.fake",
    contact_phone: "+971 2 555 0102",
    category: "IT Equipment",
  },
  {
    id: "96a97c87-f84b-5d76-9a2e-e8bd45a4824d",
    odoo_id: 3,
    name: "Oasis Facility Services",
    trn: "100000000000003",
    payment_terms_days: 45,
    lead_time_days: 7,
    address: "Building 7, ICAD 1, Musaffah South, Abu Dhabi, UAE",
    contact_email: "contracts@oasis-facilities.fake",
    contact_phone: "+971 2 555 0103",
    category: "Facility Services",
  },
  {
    id: "264c4c72-f254-5463-b3d4-6558b3a242bc",
    odoo_id: 4,
    name: "Desert Build Materials",
    trn: "100000000000004",
    payment_terms_days: 60,
    lead_time_days: 10,
    address: "Plot 88, Mina Zayed Port Commercial District, Abu Dhabi, UAE",
    contact_email: "sales@desertbuild.fake",
    contact_phone: "+971 2 555 0104",
    category: "Site Materials",
  },
  {
    id: "53ce6b6e-02ae-57b8-aa27-b03d44464786",
    odoo_id: 5,
    name: "Corniche Electrical Co.",
    trn: "100000000000005",
    payment_terms_days: 30,
    lead_time_days: 4,
    address: "Ground Floor, Corniche Towers, Al Danah, Abu Dhabi, UAE",
    contact_email: "info@corniche-electrical.fake",
    contact_phone: "+971 2 555 0105",
    category: "Electrical & IT Supplies",
  },
  {
    id: "22a12d13-2eb6-5150-af3c-2e6b721261ff",
    odoo_id: 6,
    name: "Sandstone Furniture LLC",
    trn: "100000000000006",
    payment_terms_days: 45,
    lead_time_days: 14,
    address: "Showroom 3, Airport Road, Al Rawdah, Abu Dhabi, UAE",
    contact_email: "orders@sandstone-furniture.fake",
    contact_phone: "+971 2 555 0106",
    category: "Office Furniture",
  },
];

export function getVendorById(id: string | null | undefined): SeededVendor | undefined {
  if (!id) return undefined;
  return SEEDED_VENDORS.find((v) => v.id.toLowerCase() === id.toLowerCase());
}

export function getVendorByName(name: string | null | undefined): SeededVendor | undefined {
  if (!name) return undefined;
  const target = name.trim().toLowerCase();
  return SEEDED_VENDORS.find((v) => v.name.toLowerCase() === target);
}

export function getVendorByTrn(trn: string | null | undefined): SeededVendor | undefined {
  if (!trn) return undefined;
  const cleaned = trn.replace(/\D/g, "");
  return SEEDED_VENDORS.find((v) => v.trn === cleaned);
}
