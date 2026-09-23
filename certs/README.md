# GigaChat TLS certificate

Public Russian Trusted Root CA, downloaded over verified HTTPS on 2026-09-19.
Source: https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
Provider instructions: https://developers.sber.ru/docs/ru/gigachat/certificates

Set `GIGACHAT_CA_BUNDLE` in your local `.env` to the absolute path of
`russian_trusted_root_ca.pem`. The GigaChat client uses it for OAuth and inference.
TLS verification remains enabled; no operating-system trust store was modified.
This public certificate contains no private key or API credentials.

SHA-256 of the downloaded PEM: `936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504`
