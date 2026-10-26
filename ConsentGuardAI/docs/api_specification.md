# ConsentGuardAI — API Specification

## 1. Overview

ConsentGuardAI exposes HTTP endpoints through a Flask application. The API accepts JSON requests and returns JSON responses.

Base URL for local development:

`http://127.0.0.1:5000`

## 2. Homepage

### GET /

Checks whether the application is running.

Example success response:

```json
{
  "message": "ConsentGuardAI is running!",
  "status": "success"
}
```

## 3. Consent Management

### POST /api/consent/

Grants consent for specified data categories and a purpose.

Example request:

```json
{
  "user_id": "user-1",
  "purpose": "customer_support",
  "data_categories": ["profile", "email"]
}
```

A successful response includes the consent identifier and the consent details. Invalid requests return an error response.

### GET /api/consent/{consent_id}

Retrieves a consent record using its identifier.

### Consent withdrawal

The consent routes also provide an endpoint for withdrawing consent. Refer to `app/routes/consent_routes.py` for the exact route and request format.

## 4. Authorization

### POST /api/authorization/check

Checks whether a requested data use is authorized based on the user's consent and the requested purpose and data categories.

The response includes an authorization result and relevant decision information.

Refer to `app/routes/authorization_routes.py` for the exact request schema.

## 5. GenAI Gateway

### POST /api/genai/generate

Checks authorization and filters a prompt before passing it to the configured AI provider.

Example request:

```json
{
  "user_id": "user-1",
  "purpose": "customer_support",
  "data_category": "profile",
  "prompt": "Explain artificial intelligence simply."
}
```

Example success response using the development mock provider:

```json
{
  "response": "Mock AI response: Your request was received. Connect a real AI provider to generate an actual answer.",
  "authorized": true,
  "purpose": "customer_support",
  "data_category": "profile"
}
```

## 6. Error Responses

The GenAI endpoint may return:

- **400 Bad Request:** Invalid JSON, missing fields, invalid input, or a gateway failure.
- **403 Forbidden:** Authorization denied because matching active consent was not found.
- **503 Service Unavailable:** The authorization check could not be completed.

Other endpoints may use additional status codes depending on their implementation.

## 7. Security Notes

- Send JSON requests with `Content-Type: application/json`.
- Do not include passwords, API keys, or other secrets in prompts.
- Authorization must succeed before the GenAI gateway processes the prompt.
- The mock provider is for development and does not call a real AI model.

**Implementation note:** Verify the exact route paths, validation rules, and response schemas against the current Flask route files before publishing this specification as final API documentation.