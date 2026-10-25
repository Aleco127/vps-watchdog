#!/usr/bin/env python3
"""Watchdog EXTERNO del VPS de Zook (srv1090924 / mail.zook.mx), corre en GitHub Actions.

El monitor interno (/root/mail-monitor.py en el VPS) no puede avisar si se cae el VPS completo
o si su cron deja de correr. Este script lo vigila desde fuera:
  - señal de vida del monitor: https://mail.zook.mx/monitor.json con menos de 20 min
  - IMAP 993 y SMTP 465 responden con TLS válido
  - https://zook.mx responde
Avisa por Telegram al caerse (tras reintentar 90 s después) y al recuperarse. El estado
"caído" es un issue abierto con la etiqueta `caido` (así no repite el aviso cada corrida).
"""
import json, os, socket, ssl, time, urllib.parse, urllib.request

HOST = "mail.zook.mx"
HEARTBEAT_URL = f"https://{HOST}/monitor.json"
HEARTBEAT_MAX_AGE = 20 * 60
REPO = os.environ.get("GITHUB_REPOSITORY", "")
GH = os.environ.get("GITHUB_TOKEN", "")


def tls_banner(port, expect):
    ctx = ssl.create_default_context()
    with socket.create_connection((HOST, port), timeout=15) as s, ctx.wrap_socket(s, server_hostname=HOST) as t:
        b = t.recv(200)
        if not b.startswith(expect):
            raise RuntimeError(f"saludo inesperado {b[:40]!r}")


def checks():
    bad = []
    try:
        with urllib.request.urlopen(HEARTBEAT_URL, timeout=20) as r:
            hb = json.load(r)
        age = time.time() - hb["ts"]
        if age > HEARTBEAT_MAX_AGE:
            bad.append(f"el monitor interno no corre desde hace {int(age // 60)} min")
    except Exception as e:
        bad.append(f"sin señal de vida del monitor ({str(e)[:60]})")
    for port, expect, name in ((993, b"* OK", "IMAP 993"), (465, b"220", "SMTP 465")):
        try:
            tls_banner(port, expect)
        except Exception as e:
            bad.append(f"{name}: {str(e)[:60]}")
    try:
        urllib.request.urlopen("https://zook.mx/", timeout=20).read(100)
    except Exception as e:
        bad.append(f"https://zook.mx: {str(e)[:60]}")
    if os.environ.get("SIMULAR_CAIDA") == "true":  # prueba del aviso desde "Run workflow"
        bad.append("caída SIMULADA (prueba del watchdog, ignorar)")
    return bad


def gh(method, path, body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}", method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"null")


def telegram(text):
    data = urllib.parse.urlencode({"chat_id": os.environ["TELEGRAM_CHAT"], "text": text, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT']}/sendMessage", data, timeout=20)


def main():
    bad = checks()
    if bad:
        time.sleep(90)  # no avisar por un parpadeo
        bad = checks()
    open_issues = gh("GET", "/issues?state=open&labels=caido")
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    if bad and not open_issues:
        detail = "\n".join(f"• {b}" for b in bad)
        gh("POST", "/issues", {"title": f"VPS caído {now}", "body": detail, "labels": ["caido"]})
        telegram(f"🚨 <b>Watchdog externo: el VPS no responde bien</b>\n🖥️ srv1090924 / {HOST}\n⏰ {now}\n\n{detail}\n\n"
                 "El monitor interno no puede avisar si el VPS completo está caído. Revisa hPanel de Hostinger.")
    elif not bad and open_issues:
        for i in open_issues:
            gh("POST", f"/issues/{i['number']}/comments", {"body": f"Recuperado {now}"})
            gh("PATCH", f"/issues/{i['number']}", {"state": "closed"})
        telegram(f"✅ <b>Watchdog externo: VPS recuperado</b>\n🖥️ srv1090924 / {HOST}\n⏰ {now}")
    print("FALLAS:" if bad else "OK", *bad, sep="\n  ")


if __name__ == "__main__":
    main()
