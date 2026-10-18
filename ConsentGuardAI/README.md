# ConsentGuardAI

**A purpose-based authorization system for secure reuse of user data in Generative AI.**

ConsentGuardAI is a research and development project exploring how a system can check a proposed use of user data against the original purpose, applicable restrictions, and purpose-specific consent before data is sent to a Generative AI provider.

> **Project status:** Initial project structure / work in progress. Do not describe security controls as production-ready until they have been implemented and tested.

## Main goals

- Register user-provided records with an original purpose and restrictions.
- Manage purpose-specific consent, including withdrawal.
- Compare original and proposed purposes using semantic similarity as a supporting signal.
- Enforce policy rules that take priority over similarity scores.
- Return an `ALLOW`, `WARN`, or `BLOCK` decision with an explanation.
- Protect sensitive content and minimize data sent to external AI providers.
- Record authorization events for auditing and evaluate the system with labeled test cases.

## Architecture

- `app/` — Flask application factory, routes, configuration and request middleware.
- `security/` — Authentication, access control, input validation and encryption helpers.
- `consent/` — Consent lifecycle and repository logic.
- `policy_engine/` — Purpose comparison and authorization rules.
- `database/` — Database models, connections, repositories and schema migrations.
- `audit/` — Audit events and integrity checks.
- `genai_gateway/` — Controlled integration with an external AI provider.
- `frontend/` — HTML templates, CSS and JavaScript.
- `tests/` — Functional and security tests.
- `evaluation/` — Labeled test cases and research evaluation scripts.
- `docs/` — Architecture, API specification and threat model.

## Prerequisites

- Python 3.11 or a compatible version supported by the selected dependencies.
- PostgreSQL for the intended multi-user deployment.
- Git and a GitHub account for collaboration.
- VS Code or another Python editor.

SQLite may be used for isolated early experiments if the application configuration explicitly supports it. The intended shared application database is PostgreSQL.

## Local setup

1. Create and activate a virtual environment.

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies.

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Create a local environment file by copying `.env.example` to `.env`, then set unique local secrets and a valid PostgreSQL connection string. Do not commit `.env`.

4. Create the PostgreSQL database and database user. Give the application only the permissions it needs.

5. Implement/configure the application factory `create_app()` in `app/__init__.py` and the configuration, models, and migrations before expecting the server to run.

6. Once the application factory and configuration are implemented, start the development server:

   ```bash
   python run.py
   ```

   The server entry point depends on `app.create_app` existing. The project will not run end-to-end until the application modules are implemented and configured.

## Database migrations

Use Flask-Migrate/Alembic to create versioned schema migrations after the database models are defined. Do not create fake migration scripts by hand. Review migration contents before applying them to a shared database.

## Security and privacy notes

- Use fictional data during development and demonstrations.
- Keep `.env`, API keys, database credentials, encryption keys, local databases, and backups out of GitHub.
- Keep encryption keys separate from encrypted records; use a proper key-management solution for deployment.
- Enforce authentication and record ownership in the backend, not only in the browser.
- Do not send protected content to a GenAI provider unless the server-side policy decision permits it.
- A semantic similarity score is not proof of consent or authorization.
- Minimize audit data: avoid recording raw sensitive content or full prompts unless strictly necessary and explicitly designed for.
- Configure the selected AI provider's data-retention and training settings; application controls cannot guarantee that a third-party provider never retains data.
- Use HTTPS, secure session settings, least-privilege database credentials, protected backups, and appropriate key rotation before deployment.

## Team workflow

1. Agree on API contracts, database fields, consent states, and function signatures.
2. Use a separate Git branch for each contributor's work.
3. Commit small, focused changes and open pull requests for review.
4. Never commit secrets, real user data, local database files, or unreviewed generated evaluation results.
5. Run the tests before merging changes.

## Evaluation plan

Prepare labeled examples for permitted, ambiguous, and prohibited purpose changes. Evaluate authorization correctness separately from NLP similarity performance. Report false-allow and false-block rates, precision, recall, and processing latency based on actual experiments.

## License

Add the license selected by the project team or institution before public release.
