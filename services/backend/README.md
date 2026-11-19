# Procurement Document Assistant - Backend Service

FastAPI REST API and background worker for document processing, approvals, and matching.

## Try the extraction pipeline

Follow these steps to run and verify the document extraction pipeline end-to-end against the local Docker stack:

### 1. Stack Setup & Data Initialization

```bash
# Generate .env with local passwords and JWT secrets (if .env does not exist)
make env

# Start local stack: PostgreSQL (pgvector), Azurite, API, and Worker
make up

# Seed master data (vendors, products, settings, departments, demo accounts)
make seed

# Generate synthetic evaluation PDFs and replay fixtures
make datagen
```

### 2. Log in as Buyer 1

```bash
BUYER_TOKEN=$(curl -s -X POST http://localhost:8013/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "buyer1@demo-holdings.example", "password": "'"${DEMO_USER_PASSWORD}"'"}' \
  | jq -r .access_token)
```

Output:
```json
{
  "access_token": "<TOKEN>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 3. Upload S1 Quotation (`s1-quote-gulfline.pdf`)

Upload the vendor quote to enqueue the extraction job:

```bash
UPLOAD_RESP=$(curl -s -X POST http://localhost:8013/api/v1/documents \
  -H "Authorization: Bearer ${BUYER_TOKEN}" \
  -F "file=@tools/datagen/out/s1-quote-gulfline.pdf" \
  -F "doc_type=quote")
echo "${UPLOAD_RESP}" | jq .
DOC_ID=$(echo "${UPLOAD_RESP}" | jq -r .id)
```

Output:
```json
{
  "id": "805a1c59-c0c3-400f-ac4f-830c912f2414",
  "status": "queued"
}
```

Wait ~2 seconds for the background worker to process the job:

```bash
# Fetch document metadata
curl -s http://localhost:8013/api/v1/documents/${DOC_ID} \
  -H "Authorization: Bearer ${BUYER_TOKEN}" | jq '{id: .id, status: .status, vendor_id: .vendor_id, suspicious: .suspicious}'
```

Output:
```json
{
  "id": "805a1c59-c0c3-400f-ac4f-830c912f2414",
  "status": "needs_review",
  "vendor_id": "5cba38c7-118b-5996-a309-80ce9ddf0b49",
  "suspicious": false
}
```

Fetch extraction details showing vendor Gulf Line IT Trading and total 28875.00:

```bash
curl -s http://localhost:8013/api/v1/documents/${DOC_ID}/extraction \
  -H "Authorization: Bearer ${BUYER_TOKEN}" \
  | jq '.fields[] | select(.name=="vendor_name" or .name=="total") | {name: .name, value_raw: .value_raw, status: .status}'
```

Output:
```json
{
  "name": "vendor_name",
  "value_raw": "Gulf Line IT Trading",
  "status": "ok"
}
{
  "name": "total",
  "value_raw": "28875.00",
  "status": "ok"
}
```

Confirm the document as Buyer:

```bash
curl -s -X POST http://localhost:8013/api/v1/documents/${DOC_ID}/confirm \
  -H "Authorization: Bearer ${BUYER_TOKEN}" | jq .
```

Output:
```json
{
  "id": "805a1c59-c0c3-400f-ac4f-830c912f2414",
  "status": "confirmed"
}
```

### 4. Upload S7 Prompt Injection Invoice (`s7-inv-7001-inj.pdf`)

Upload the injection scenario invoice containing malicious instructions:

```bash
INJ_RESP=$(curl -s -X POST http://localhost:8013/api/v1/documents \
  -H "Authorization: Bearer ${BUYER_TOKEN}" \
  -F "file=@tools/datagen/out/s7-inv-7001-inj.pdf" \
  -F "doc_type=invoice")
INJ_DOC_ID=$(echo "${INJ_RESP}" | jq -r .id)
```

Wait ~2 seconds for worker processing, then inspect metadata:

```bash
curl -s http://localhost:8013/api/v1/documents/${INJ_DOC_ID} \
  -H "Authorization: Bearer ${BUYER_TOKEN}" | jq '{id: .id, status: .status, suspicious: .suspicious}'
```

Output:
```json
{
  "id": "1672fb42-10be-4d46-82f7-e559cdb9369d",
  "status": "needs_review",
  "suspicious": true
}
```

Verify that the total remained 2625.00 (ground truth, unaltered by prompt injection):

```bash
curl -s http://localhost:8013/api/v1/documents/${INJ_DOC_ID}/extraction \
  -H "Authorization: Bearer ${BUYER_TOKEN}" \
  | jq '.fields[] | select(.name=="total") | {name: .name, value_raw: .value_raw}'
```

Output:
```json
{
  "name": "total",
  "value_raw": "2625.00"
}
```

Confirm attempt is blocked with 409 Conflict:

```bash
curl -s -X POST http://localhost:8013/api/v1/documents/${INJ_DOC_ID}/confirm \
  -H "Authorization: Bearer ${BUYER_TOKEN}" | jq .
```

Output:
```json
{
  "type": "https://pda.example/errors/flags-open",
  "title": "Cannot Confirm Document",
  "status": 409,
  "code": "FLAGS_OPEN",
  "detail": "Document has 0 open flag(s)",
  "request_id": "aebf447612dc4817acef09dd6fdf929f",
  "errors": [
    {
      "name": "suspicious",
      "message": "Document flagged as suspicious"
    }
  ]
}
```

### 5. Access Scope Checks (Requester)

Log in as Requester (`requester.fac@demo-holdings.example`):

```bash
REQ_TOKEN=$(curl -s -X POST http://localhost:8013/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "requester.fac@demo-holdings.example", "password": "'"${DEMO_USER_PASSWORD}"'"}' \
  | jq -r .access_token)
```

Fetching another user's document returns 404:

```bash
curl -s -i http://localhost:8013/api/v1/documents/${INJ_DOC_ID} \
  -H "Authorization: Bearer ${REQ_TOKEN}"
```

Output:
```
HTTP/1.1 404 Not Found
content-type: application/problem+json

{"type":"https://pda.example/errors/document-not-found","title":"Document Not Found","status":404,"code":"DOCUMENT_NOT_FOUND","detail":"Document 1672fb42-10be-4d46-82f7-e559cdb9369d not found"}
```

Attempting to confirm a document returns 403 Forbidden:

```bash
curl -s -i -X POST http://localhost:8013/api/v1/documents/${INJ_DOC_ID}/confirm \
  -H "Authorization: Bearer ${REQ_TOKEN}"
```

Output:
```
HTTP/1.1 403 Forbidden
content-type: application/problem+json

{"type":"https://pda.example/errors/forbidden","title":"Forbidden","status":403,"code":"FORBIDDEN","detail":"Principal lacks permission for capability 'document.review'"}
```

### 6. Teardown

```bash
docker compose down -v
```
