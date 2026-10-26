# ConsentGuardAI — Threat Model

## 1. Purpose

This document identifies security threats that may affect ConsentGuardAI, a purpose-based authorization system for controlling the reuse of user data in Generative AI applications.

## 2. Assets to Protect

- User data and personal information
- User credentials and authentication sessions
- Consent records and consent status
- Authorization decisions
- AI prompts and generated responses
- Environment variables, encryption keys, and provider API keys
- Audit records and application configuration

## 3. Potential Threats

### 3.1 Unauthorized Data Access

**Threat:** A user or application attempts to use data without valid consent.

**Mitigation:** Check for matching active consent before allowing a GenAI request to proceed. Deny requests when authorization cannot be verified.

### 3.2 Purpose Misuse

**Threat:** Data originally provided for one purpose is reused for a different purpose without appropriate authorization.

**Mitigation:** Associate consent with a stated purpose and data categories. Compare the requested purpose with the consented purpose. Full detection of changed purposes requires additional implementation and testing.

### 3.3 Sensitive Information in Prompts

**Threat:** Prompts contain email addresses, phone numbers, credentials, or other sensitive information.

**Mitigation:** Apply prompt filtering before sending data to the provider. Pattern-based filters can miss sensitive information and may incorrectly flag harmless text, so they should not be treated as complete protection.

### 3.4 Prompt Injection

**Threat:** A prompt contains instructions intended to bypass security controls or expose hidden instructions.

**Mitigation:** Detect known unsafe phrases and keep authorization checks separate from instructions contained in user prompts. Basic phrase matching does not detect every prompt-injection attack.

### 3.5 Malformed Requests

**Threat:** Invalid or unexpected input causes application errors or unintended behavior.

**Mitigation:** Validate request types, required fields, and input values. Return appropriate error responses without exposing internal exception details.

### 3.6 Credential and Secret Exposure

**Threat:** API keys, encryption keys, passwords, or database credentials are exposed through source control or logs.

**Mitigation:** Store secrets in environment variables, exclude local `.env` files from Git, provide safe placeholders in `.env.example`, and rotate any exposed credentials.

### 3.7 Excessive Requests

**Threat:** An attacker sends repeated requests to exhaust application resources.

**Mitigation:** Apply rate limiting and monitor unusual request patterns.

### 3.8 Inadequate Auditability

**Threat:** Unauthorized access or consent changes cannot be investigated because relevant events were not recorded.

**Mitigation:** Record appropriate authorization and consent events while avoiding unnecessary sensitive data in logs. Protect audit records against unauthorized modification.

## 4. Trust Boundaries

- **Client to Flask API:** Treat all client input as untrusted.
- **API to authorization service:** Require a valid authorization decision before processing protected data.
- **Gateway to AI provider:** Send prompts only after authorization and filtering checks succeed.
- **Application to database:** Protect stored records and credentials through