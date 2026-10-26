# ConsentGuardAI — System Architecture

## 1. Overview

ConsentGuardAI is a purpose-based authorization system designed to help prevent the unauthorized reuse of user data in Generative AI (GenAI) applications.

The system checks whether a user's consent covers the requested purpose and data category before allowing a prompt to reach the AI gateway.

## 2. Main Components

- **Frontend:** Provides pages and forms for login, registration, consent management, records, authorization checks, and audit information.
- **Flask Application:** Receives HTTP requests and connects the frontend to backend services.
- **Authentication Module:** Supports user authentication.
- **Consent Service:** Grants, retrieves, and withdraws user consent.
- **Policy and Authorization Engine:** Checks whether the requested data use matches active consent.
- **GenAI Gateway:** Filters prompts and forwards approved requests to a configured AI provider.
- **Database Layer:** Stores application records, including consent-related information.
- **Evaluation Module:** Runs test cases and produces evaluation metrics and comparison results.

## 3. Request Flow

1. A user submits a request with a user ID, purpose, data category, and prompt.
2. The Flask API validates the request.
3. The authorization service checks for matching active consent.
4. If consent is missing or does not match, the request is denied.
5. If authorization succeeds, the prompt filter checks for common sensitive-data patterns and potentially unsafe instructions.
6. The gateway sends an accepted prompt to the configured AI provider.
7. The API returns the result or an appropriate error response.

## 4. Security Controls

- Validate incoming request data.
- Check consent before processing GenAI requests.
- Reject prompts containing detected sensitive information or known unsafe instruction patterns.
- Use security headers and rate limiting.
- Keep secrets in environment variables rather than source code.
- Record and evaluate authorization decisions where audit functionality is configured.

## 5. Current Implementation Notes

The current gateway uses a mock AI provider for development and testing. It does not generate real AI responses until a real provider is configured.

The prompt filter uses basic pattern matching. It is not a complete guarantee against prompt injection or sensitive-data leakage.

The system currently supports basic consent-based allow/deny decisions. Purpose-reuse detection and a complete Allow/Warn/Block workflow require separate implementation and evaluation.

## 6. Future Improvements

- Add purpose extraction and comparison for previously collected data.
- Implement configurable Allow, Warn, and Block outcomes.
- Integrate a real AI provider securely.
- Improve audit logging and dashboard reporting.
- Evaluate filtering and authorization accuracy using documented test cases.