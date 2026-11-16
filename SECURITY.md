# Security

Supported: latest published community preview. Report vulnerabilities privately through
GitHub private vulnerability reporting when enabled. Otherwise open a minimal issue asking
for a private contact without exposing exploit details or private data.

Never publish API keys, raw diagnostics exports, customer IDs, device identifiers or signed
URLs. Revoke an exposed key in Testo immediately. Home Assistant config storage, integration
cache, recorder and backups contain private data and require access protection.

Downloads use only HTTPS on documented Testo S3 result hosts, without API authentication
headers. No redirects, device mutations, alarm acknowledgements or arbitrary API base URLs.
