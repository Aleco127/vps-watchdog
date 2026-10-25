# vps-watchdog

Vigilancia **externa** del VPS de Zook (`mail.zook.mx`). Corre cada ~10 min en GitHub Actions y avisa por Telegram si:

- el monitor interno del VPS deja de reportarse (`https://mail.zook.mx/monitor.json` con más de 20 min de antigüedad),
- IMAP 993 o SMTP 465 no responden con TLS válido,
- `https://zook.mx` no responde.

Cubre lo que el monitor interno no puede ver: que se caiga el VPS completo o que se detenga su cron. Mientras dura una caída hay un issue abierto con la etiqueta `caido`; se cierra solo al recuperarse.

- Secretos del repo: `TELEGRAM_BOT`, `TELEGRAM_CHAT` (mismo bot que los avisos del VPS).
- Correrlo a mano: pestaña Actions → watchdog → *Run workflow*.
- El job `keepalive` hace un commit al mes para que GitHub no desactive el cron por inactividad.
