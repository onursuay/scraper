#!/usr/bin/env python3
"""SMTP ile e-posta adresi dogrulama (liste hijyeni).

Neden: "tahmin" tipindeki adresler (MX kaydi var diye uretilen info@alanadi)
gercekten var mi bilinmiyor. Dogrulanmadan gonderim yapilirsa bounce orani
yukselir ve gonderen alan adinin itibari duser.

Yontem: alan adinin MX sunucusuna baglanip zarf seviyesinde RCPT TO sorgusu
yapilir; POSTA GONDERILMEZ (DATA asamasina hic gecilmez, oturum RSET+QUIT ile
kapatilir).

Sonuc siniflari:
  gecerli   - sunucu adresi kabul etti (ve alan adi catch-all DEGIL)
  gecersiz  - sunucu adresi reddetti (kalici 5xx)
  belirsiz  - catch-all alan adi, greylisting, zaman asimi veya baglanti hatasi
"""
import random
import smtplib
import socket
import string
import time

import dns.resolver

HELO = "srv1622864.hstgr.cloud"
GONDEREN = ""  # bos zarf gondereni (bounce standardi)
ZAMAN_ASIMI = 12

_mx_onbellek = {}
_catchall_onbellek = {}


def mx_sunuculari(alan: str) -> list:
    if alan in _mx_onbellek:
        return _mx_onbellek[alan]
    try:
        yanit = dns.resolver.resolve(alan, "MX", lifetime=8)
        mx = [str(r.exchange).rstrip(".") for r in sorted(yanit, key=lambda r: r.preference)]
    except Exception:
        mx = []
    _mx_onbellek[alan] = mx
    return mx


def _rcpt_sor(sunucu: str, adresler: list) -> dict:
    """Tek oturumda birden fazla adresi sorar. POSTA GONDERMEZ."""
    sonuc = {}
    try:
        s = smtplib.SMTP(timeout=ZAMAN_ASIMI)
        s.connect(sunucu, 25)
        s.ehlo(HELO)
        try:
            s.starttls()
            s.ehlo(HELO)
        except Exception:
            pass
        s.docmd("MAIL", f"FROM:<{GONDEREN}>")
        for a in adresler:
            try:
                kod, _ = s.docmd("RCPT", f"TO:<{a}>")
            except Exception:
                kod = 0
            sonuc[a] = kod
        try:
            s.docmd("RSET")
            s.quit()
        except Exception:
            pass
    except (socket.error, smtplib.SMTPException, OSError):
        pass
    return sonuc


def catchall_mi(alan: str, sunucu: str) -> bool:
    if alan in _catchall_onbellek:
        return _catchall_onbellek[alan]
    rastgele = "".join(random.choices(string.ascii_lowercase + string.digits, k=18))
    hedef = f"{rastgele}@{alan}"
    kod = _rcpt_sor(sunucu, [hedef]).get(hedef, 0)
    ca = 200 <= kod < 300
    _catchall_onbellek[alan] = ca
    return ca


def dogrula_toplu(adresler: list, bekleme: float = 1.5) -> dict:
    """Adresleri alan adina gore gruplayip dogrular."""
    gruplar = {}
    for a in adresler:
        a = (a or "").strip().lower()
        if "@" in a:
            gruplar.setdefault(a.split("@", 1)[1], []).append(a)

    sonuc = {}
    for alan, liste in gruplar.items():
        mx = mx_sunuculari(alan)
        if not mx:
            for a in liste:
                sonuc[a] = ("gecersiz", "MX kaydı yok")
            continue

        sunucu = mx[0]
        if catchall_mi(alan, sunucu):
            for a in liste:
                sonuc[a] = ("belirsiz", "catch-all alan adı")
            time.sleep(bekleme)
            continue

        kodlar = _rcpt_sor(sunucu, liste)
        for a in liste:
            kod = kodlar.get(a, 0)
            if 200 <= kod < 300:
                sonuc[a] = ("gecerli", f"SMTP {kod}")
            elif 500 <= kod < 600:
                sonuc[a] = ("gecersiz", f"SMTP {kod}")
            elif kod == 0:
                sonuc[a] = ("belirsiz", "bağlantı kurulamadı")
            else:
                sonuc[a] = ("belirsiz", f"SMTP {kod}")
        time.sleep(bekleme)
    return sonuc
