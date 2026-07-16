# Tableau API Connector (Odoo Module)

**Company:** Infintor Solutions

This Odoo module exposes a secure, token-based API endpoint for Tableau integration.

## Features
- API endpoint returns  data in JSON format.
- Access protected by Bearer token (managed via Odoo backend UI).
- UI for managing tokens (create, activate, deactivate, assign to user).
- Permission group for API token management.

## Usage
1. Install this module.
2. Assign users to the **Tableau API Managerr** group.
3. Go to **Tableau API > API Tokens** to create/manage tokens.
4. Create Model records and assighn models and fields.

## Endpoint Example

```
GET http://<your-odoo-server>/api/tbtables
Authorization: Bearer <token>
```

## Security
- Only tokens marked as "Active" will work.
- Each token is linked to a user for auditing.

---