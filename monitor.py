#!/usr/bin/env python3
"""
Pokemon Center ETB Monitor — versao Railway (24/7)
Credenciais lidas via variaveis de ambiente.
"""

import asyncio
import aiohttp
import smtplib
import re
import os
import logging
import urllib.request
import urllib.parse
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

# ── Logging simples (Railway exibe no painel Logs) ────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etb-monitor")

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACOES — lidas de variaveis de ambiente
#  Defina-as no painel Railway > Variables
# ══════════════════════════════════════════════════════════════════════════════

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
TIMEOUT        = int(os.getenv("TIMEOUT", "15"))

# Email
GMAIL_REMETENTE    = os.getenv("GMAIL_REMETENTE", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO", "")
EMAIL_ATIVO        = bool(GMAIL_REMETENTE and GMAIL_APP_PASSWORD and EMAIL_DESTINATARIO)

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")

# WhatsApp
WHATSAPP_DE    = os.getenv("WHATSAPP_DE", "whatsapp:+14155238886")
WHATSAPP_PARA  = os.getenv("WHATSAPP_PARA", "")
WHATSAPP_ATIVO = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and WHATSAPP_PARA)

# SMS
SMS_DE    = os.getenv("SMS_DE", "")
SMS_PARA  = os.getenv("SMS_PARA", "")
SMS_ATIVO = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and SMS_DE and SMS_PARA)

# ── URLs ──────────────────────────────────────────────────────────────────────
POKEMON_CENTER_URL = "https://www.pokemoncenter.com"
ETB_SEARCH_URL     = "https://www.pokemoncenter.com/en-us/search?q=elite+trainer+box&inStockOnly=false"
ETB_CATEGORY_URL   = "https://www.pokemoncenter.com/en-us/category/elite-trainer-boxes"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":           "pt-BR,pt;q=0.9,en-US;q=0.8",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control":             "no-cache",
    "Pragma":                    "no-cache",
}


# ══════════════════════════════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_email(products: list):
    if not EMAIL_ATIVO:
        log.info("Email desativado (variaveis nao configuradas).")
        return
    try:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        linhas_html = ""
        for p in products:
            estoque = "Disponivel" if p["in_stock"] else "Esgotado"
            cor     = "#16a34a" if p["in_stock"] else "#dc2626"
            link    = (f'<a href="{p["url"]}" style="color:#f59e0b;text-decoration:none;">{p["name"]}</a>'
                       if p["url"] else p["name"])
            linhas_html += (
                f'<tr>'
                f'<td style="padding:10px;border-bottom:1px solid #374151;">{link}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #374151;text-align:center;">{p["price"]}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #374151;text-align:center;'
                f'color:{cor};font-weight:bold;">{estoque}</td>'
                f'</tr>'
            )

        html_body = f"""
<html><body style="margin:0;padding:0;background:#111827;font-family:Arial,sans-serif;color:#f9fafb;">
<div style="max-width:600px;margin:30px auto;background:#1f2937;border-radius:12px;
            overflow:hidden;border:1px solid #374151;">

  <div style="background:linear-gradient(135deg,#f59e0b,#d97706);padding:24px;text-align:center;">
    <h1 style="margin:0;font-size:24px;color:#111827;">Pokemon Center ETB Monitor</h1>
    <p style="margin:6px 0 0;color:#111827;opacity:0.8;">Elite Trainer Box detectada!</p>
  </div>

  <div style="padding:24px;">
    <p style="color:#9ca3af;margin:0 0 16px;">
      Detectado em: <strong style="color:#f9fafb;">{agora}</strong>
    </p>
    <table style="width:100%;border-collapse:collapse;background:#111827;border-radius:8px;">
      <thead><tr style="background:#374151;">
        <th style="padding:12px;text-align:left;color:#f59e0b;">Produto</th>
        <th style="padding:12px;text-align:center;color:#f59e0b;">Preco</th>
        <th style="padding:12px;text-align:center;color:#f59e0b;">Estoque</th>
      </tr></thead>
      <tbody>{linhas_html}</tbody>
    </table>
    <div style="margin-top:24px;text-align:center;">
      <a href="{ETB_SEARCH_URL}"
         style="background:#f59e0b;color:#111827;padding:12px 28px;border-radius:8px;
                text-decoration:none;font-weight:bold;font-size:15px;">
        Ver no Pokemon Center
      </a>
    </div>
  </div>

  <div style="padding:16px;text-align:center;color:#6b7280;font-size:12px;border-top:1px solid #374151;">
    Pokemon Center ETB Monitor — Notificacao automatica via Railway
  </div>
</div>
</body></html>"""

        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"ETB Encontrada! {len(products)} produto(s) — Pokemon Center"
        msg["From"]    = GMAIL_REMETENTE
        msg["To"]      = EMAIL_DESTINATARIO
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_REMETENTE, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())

        log.info(f"Email enviado para {EMAIL_DESTINATARIO}")

    except smtplib.SMTPAuthenticationError:
        log.error("Email: falha de autenticacao Gmail. Verifique GMAIL_APP_PASSWORD.")
    except Exception as e:
        log.error(f"Email erro: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  TWILIO (WhatsApp + SMS) — sem SDK, puro urllib
# ══════════════════════════════════════════════════════════════════════════════

def _twilio_post(payload: dict) -> bool:
    url  = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    cred = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
    req  = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {cred}")
    req.add_header("Content-Type",  "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status in (200, 201)
            if not ok:
                log.warning(f"Twilio respondeu HTTP {resp.status}")
            return ok
    except Exception as e:
        log.error(f"Twilio erro: {e}")
        return False


def send_whatsapp(products: list):
    if not WHATSAPP_ATIVO:
        log.info("WhatsApp desativado (variaveis nao configuradas).")
        return
    nomes = "\n".join(f"- {p['name']} ({p['price']})" for p in products[:5])
    corpo = f"ETB ENCONTRADA!\n\n{nomes}\n\nVer agora: {ETB_SEARCH_URL}"
    if _twilio_post({"From": WHATSAPP_DE, "To": WHATSAPP_PARA, "Body": corpo}):
        log.info(f"WhatsApp enviado para {WHATSAPP_PARA}")


def send_sms(products: list):
    if not SMS_ATIVO:
        log.info("SMS desativado (variaveis nao configuradas).")
        return
    nomes = ", ".join(p["name"][:25] for p in products[:3])
    corpo = f"ETB: {nomes} | {ETB_SEARCH_URL}"
    if _twilio_post({"From": SMS_DE, "To": SMS_PARA, "Body": corpo}):
        log.info(f"SMS enviado para {SMS_PARA}")


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPING
# ══════════════════════════════════════════════════════════════════════════════

class PokemonCenterMonitor:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.found_etbs: list   = []
        self.check_count        = 0
        self.start_time         = datetime.now()
        self.last_check: Optional[datetime] = None
        self.notified_ids: set  = set()

    async def create_session(self):
        connector    = aiohttp.TCPConnector(ssl=False, limit=10, ttl_dns_cache=300)
        timeout      = aiohttp.ClientTimeout(total=TIMEOUT, connect=5)
        self.session = aiohttp.ClientSession(headers=HEADERS, connector=connector, timeout=timeout)

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                log.warning(f"HTTP {response.status} em {url}")
                return None
        except asyncio.TimeoutError:
            log.warning("Timeout na requisicao")
            return None
        except aiohttp.ClientError as e:
            log.warning(f"Erro de rede: {e}")
            return None

    def parse_etbs_from_html(self, html: str) -> list:
        soup      = BeautifulSoup(html, "html.parser")
        products  = []
        selectors = [
            "div[class*='product-tile']", "div[class*='product-card']",
            "li[class*='product']",       "article[class*='product']",
            "[data-testid*='product']",   "div[class*='ProductTile']",
            "div[class*='tile']",
        ]
        items = []
        for sel in selectors:
            items = soup.select(sel)
            if items:
                break

        if not items:
            for link in soup.find_all("a", href=re.compile(r"elite.trainer", re.IGNORECASE)):
                name = link.get_text(strip=True) or link.get("title", "ETB Encontrada")
                href = link.get("href", "")
                if href and not href.startswith("http"):
                    href = POKEMON_CENTER_URL + href
                if name and href:
                    products.append({
                        "id": href, "name": name[:80], "url": href,
                        "price": "Ver site", "in_stock": True,
                        "found_at": datetime.now().strftime("%H:%M:%S"),
                    })
            return products

        for item in items:
            try:
                name_el = (
                    item.select_one("[class*='name']") or item.select_one("[class*='title']") or
                    item.select_one("h2") or item.select_one("h3") or item.select_one("a")
                )
                name = name_el.get_text(strip=True) if name_el else ""
                if not re.search(r"elite.trainer", name, re.IGNORECASE):
                    continue
                link_el  = item.select_one("a[href]")
                href     = link_el["href"] if link_el else ""
                if href and not href.startswith("http"):
                    href = POKEMON_CENTER_URL + href
                price_el = item.select_one("[class*='price']")
                price    = price_el.get_text(strip=True) if price_el else "N/A"
                sold_out = bool(
                    item.select_one("[class*='sold-out']") or
                    item.select_one("[class*='out-of-stock']") or
                    re.search(r"sold.out|out of stock|esgotado", item.get_text(), re.IGNORECASE)
                )
                if name:
                    products.append({
                        "id": href or name, "name": name[:80], "url": href,
                        "price": price, "in_stock": not sold_out,
                        "found_at": datetime.now().strftime("%H:%M:%S"),
                    })
            except Exception:
                continue
        return products

    async def check_pokemon_center(self) -> list:
        all_products = []
        for url in [ETB_SEARCH_URL, ETB_CATEGORY_URL]:
            html = await self.fetch_page(url)
            if html:
                all_products.extend(self.parse_etbs_from_html(html))
        seen, unique = set(), []
        for p in all_products:
            if p["id"] not in seen:
                seen.add(p["id"])
                unique.append(p)
        return unique

    async def run_check(self):
        self.check_count += 1
        self.last_check   = datetime.now()
        log.info(f"Verificacao #{self.check_count} iniciada...")

        products        = await self.check_pokemon_center()
        self.found_etbs = products

        if products:
            log.info(f"{len(products)} ETB(s) encontrada(s).")
            new_items = [p for p in products if p["id"] not in self.notified_ids]
            if new_items:
                for item in new_items:
                    self.notified_ids.add(item["id"])
                names = ", ".join(i["name"][:40] for i in new_items[:3])
                log.info(f"NOVA(S) ETB: {names}")
                send_email(new_items)
                send_whatsapp(new_items)
                send_sms(new_items)
            else:
                log.info("ETBs ja notificadas anteriormente, sem novidade.")
        else:
            log.info("Nenhuma ETB encontrada nesta verificacao.")

    def get_uptime(self) -> str:
        delta  = datetime.now() - self.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    log.info("=== Pokemon Center ETB Monitor iniciado (Railway) ===")
    log.info(f"Intervalo: {CHECK_INTERVAL}s | Email: {EMAIL_ATIVO} | WhatsApp: {WHATSAPP_ATIVO} | SMS: {SMS_ATIVO}")

    monitor = PokemonCenterMonitor()
    await monitor.create_session()

    try:
        while True:
            await monitor.run_check()
            log.info(f"Proxima verificacao em {CHECK_INTERVAL}s. Uptime: {monitor.get_uptime()}")
            await asyncio.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        log.info("Monitor encerrado pelo usuario.")
    except Exception as e:
        log.error(f"Erro inesperado: {e}")
        raise
    finally:
        await monitor.close_session()


if __name__ == "__main__":
    asyncio.run(main())
