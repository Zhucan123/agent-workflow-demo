# Security & Data Handling

Customer data is encrypted in transit with TLS 1.3 and at rest with
AES-256. Backups are created every 6 hours and retained for 30 days.

Access to production data requires multi-factor authentication and is
audited. Role-based access control (RBAC) limits data exposure to the
minimum required for each role.

LLM providers receive only the content of the current conversation;
credentials are never sent to model endpoints. Conversation retention
can be disabled per workspace. Deletion requests are honored within 72
hours and propagated to all backups within 30 days.

We perform annual third-party penetration tests and publish a summary
report to all enterprise customers.