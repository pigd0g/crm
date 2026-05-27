# CRM REST API

This application exposes a JSON API under `/api/v1/` for integrations with other internal systems.

## API characteristics

- **Base path:** `/api/v1/`
- **Format:** JSON request and response bodies
- **Authentication:** none
- **CSRF:** not required for these API routes
- **Timezone:** container time is `Australia/Melbourne`

Because there is no authentication, these endpoints should only be exposed on a trusted internal network.

## Deal stages

Possible deal stage values:

| Value | Label |
| --- | --- |
| `lead` | Lead |
| `initial_outreach` | Initial outreach |
| `free_trial` | Free trial |
| `won` | Won |
| `lost` | Lost |
| `no_traction` | No traction |

## Common response structure

### Contact object

```json
{
  "id": 12,
  "first_name": "Ava",
  "last_name": "Patel",
  "full_name": "Ava Patel",
  "job_title": "Head of Sales",
  "company": "Acme",
  "email": "ava@example.com",
  "phone": "+61 400 000 000",
  "deal_ids": [3, 9],
  "created_at": "2026-05-27T01:08:21.100000+00:00",
  "updated_at": "2026-05-27T01:08:21.100000+00:00"
}
```

### Deal object

```json
{
  "id": 3,
  "name": "Northwind Trial",
  "company": "Northwind",
  "stage": "free_trial",
  "stage_label": "Free trial",
  "value": "15000.00",
  "expected_close_date": "2026-06-15",
  "description": "Priority expansion opportunity.",
  "contact_ids": [12],
  "contacts": [],
  "activities": [],
  "created_at": "2026-05-27T01:08:21.100000+00:00",
  "updated_at": "2026-05-27T01:08:21.100000+00:00"
}
```

### Error response

```json
{
  "error": "Validation failed.",
  "details": {
    "name": ["This field is required."]
  }
}
```

## Endpoints

### List stages

`GET /api/v1/stages/`

Returns the supported deal stage values for validation or dropdown generation.

**Example response**

```json
{
  "stages": [
    {"value": "lead", "label": "Lead"},
    {"value": "initial_outreach", "label": "Initial outreach"}
  ]
}
```

### List contacts

`GET /api/v1/contacts/`

**Example response**

```json
{
  "contacts": [
    {
      "id": 12,
      "first_name": "Ava",
      "last_name": "Patel",
      "full_name": "Ava Patel",
      "job_title": "Head of Sales",
      "company": "Acme",
      "email": "ava@example.com",
      "phone": "+61 400 000 000",
      "deal_ids": [3],
      "created_at": "2026-05-27T01:08:21.100000+00:00",
      "updated_at": "2026-05-27T01:08:21.100000+00:00"
    }
  ]
}
```

### Create contact

`POST /api/v1/contacts/`

**Request body**

```json
{
  "first_name": "Ava",
  "last_name": "Patel",
  "job_title": "Head of Sales",
  "company": "Acme",
  "email": "ava@example.com",
  "phone": "+61 400 000 000"
}
```

**Example curl**

```bash
curl -X POST http://localhost:8000/api/v1/contacts/ \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"Ava\",\"last_name\":\"Patel\",\"company\":\"Acme\",\"email\":\"ava@example.com\"}"
```

### Get contact

`GET /api/v1/contacts/{contact_id}/`

### Update contact

`PATCH /api/v1/contacts/{contact_id}/`

Only send the fields you want to change.

**Request body**

```json
{
  "job_title": "VP Sales",
  "phone": "+61 422 222 222"
}
```

### List deals

`GET /api/v1/deals/`

Returns each deal with linked contacts and activity history.

### Create deal

`POST /api/v1/deals/`

**Request body**

```json
{
  "name": "Northwind Trial",
  "company": "Northwind",
  "stage": "free_trial",
  "value": "15000.00",
  "expected_close_date": "2026-06-15",
  "description": "Priority expansion opportunity."
}
```

Notes:

- `name` and `company` are required
- `stage` defaults to `lead` if omitted
- `value` should be sent as a decimal string
- `expected_close_date` uses `YYYY-MM-DD`

### Get deal

`GET /api/v1/deals/{deal_id}/`

### Update deal

`PATCH /api/v1/deals/{deal_id}/`

Only send the fields you want to change.

**Request body**

```json
{
  "stage": "won",
  "value": "18000.00"
}
```

When `stage` changes, the system automatically records a `stage_change` activity entry.

### Add a note to a deal

`POST /api/v1/deals/{deal_id}/notes/`

**Request body**

```json
{
  "content": "Customer requested pricing for the annual plan."
}
```

**Response**

Returns the created activity entry.

### Link a contact to a deal

`POST /api/v1/deals/{deal_id}/contacts/`

**Request body**

```json
{
  "contact_id": 12
}
```

**Response**

Returns the full updated deal payload.

### Remove a contact from a deal

`DELETE /api/v1/deals/{deal_id}/contacts/{contact_id}/`

**Response**

Returns HTTP `204 No Content`.

## Field validation notes

- Unknown fields are rejected with HTTP `400`
- Invalid JSON is rejected with HTTP `400`
- Missing required fields return a validation error payload
- Invalid email addresses return a validation error payload
- Invalid deal stages return a validation error payload

## Integration examples

### Create a deal, then attach a contact

1. Create a contact with `POST /api/v1/contacts/`
2. Create a deal with `POST /api/v1/deals/`
3. Link them with `POST /api/v1/deals/{deal_id}/contacts/`

### Sync a stage update from another system

Send a `PATCH` request to `/api/v1/deals/{deal_id}/` with the new `stage` value. The application will both update the deal and append a stage history entry.
