# Massmail

Bulk email campaigns are managed via the `massmail` app.

## Concepts
- Email Accounts: `/massmail/email-accounts`
- Signatures: `/massmail/signatures`
- Messages: `/massmail/messages`
- Mailings: `/massmail/mailings`

## Typical Flow
1. Configure email accounts and signatures
2. Create a message (template + content)
3. Build recipients (segments or upload)
4. Launch mailing, monitor delivery and failures

## Backend Structure
- Models in `massmail/models/*`
- Admin UI in `massmail/site/*`
- Views and endpoints in `massmail/views/*`

## API
Use endpoints under `/massmail/*` (see OpenAPI).