#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Çorlu MYO - Yaz Stajı Duyuru Takip Botu
========================================
Her gün saat 00:00'da çalışır, anasayfadaki DUYURULAR bölümünü tarar,
"staj" ve "yaz" kelimelerini içeren duyuru bulursa Telegram'a bildirim gönderir.

KURULUM:
  pip install requests beautifulsoup4 schedule

KULLANIM:
  1. BOT_TOKEN ve CHAT_ID değerlerini doldurun
  2. python "staj_takip_bot (2).py"       → sürekli çalışır, 00:00'da kontrol eder
  VEYA
  2b. python "staj_takip_bot (2).py" --once  → sadece bir kez kontrol eder
"""

import sys
import io

# Windows terminalde emoji/Türkçe karakter hatası için UTF-8 zorla
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup
import schedule
import time
import re
import argparse
import warnings
from datetime import datetime, timezone, timedelta

# Türkiye saati için sabit UTC+3
TZ_TURKEY = timezone(timedelta(hours=3))

# SSL uyarılarını bastır
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ============================================================
#  ⚙️  AYARLAR — Buraya kendi bilgilerini gir
# ============================================================

BOT_TOKEN = "8755373404:AAEQua5xAoyWlZeFz2hcbL1tvXLYaUDtL34"
CHAT_ID   = "1599243581"

TARGET_URL = "https://corlumyo.nku.edu.tr/"

# Duyuru başlığında HEPSININ bulunması gereken anahtar kelimeler (küçük harf)
ANAHTAR_KELIMELER = ["staj", "yaz"]

# ============================================================


def telegram_gonder(mesaj: str) -> bool:
    """Telegram bot üzerinden mesaj gönderir."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print(f"[{datetime.now(TZ_TURKEY):%Y-%m-%d %H:%M}] ✅ Telegram mesajı gönderildi.")
        return True
    except Exception as e:
        print(f"[{datetime.now(TZ_TURKEY):%Y-%m-%d %H:%M}] ❌ Telegram hatası: {e}")
        return False


def duyurulari_cek() -> list:
    """
    Anasayfadaki DUYURULAR bölümünü tarar.
    Sadece <h6> etiketleri içinde /duyuruayrinti/ bağlantısı olan öğeleri döndürür.
    Bu sayede sol taraftaki navigasyon menüsü tamamen yoksayılır.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; StajBot/1.0)"}
        r = requests.get(TARGET_URL, timeout=20, headers=headers, verify=False)
        r.encoding = "utf-8"
    except Exception as e:
        return None, str(e)

    soup = BeautifulSoup(r.text, "html.parser")

    duyurular = []
    # Sadece <h6> içindeki, /duyuruayrinti/ URL'sine sahip linkleri al
    for h6 in soup.find_all("h6"):
        link_tag = h6.find("a", href=re.compile(r"/duyuruayrinti/"))
        if not link_tag:
            continue

        # Başlık metnini al (tarihi ve "Ayrıntı İçin Tıklayınız" kısmını temizle)
        tam_metin = h6.get_text(" ", strip=True)
        # Sondaki "... Ayrıntı İçin Tıklayınız..." kısmını kaldır
        baslik = re.sub(r"\s*\.\.\.\s*Ayrıntı.*$", "", tam_metin, flags=re.IGNORECASE).strip()
        # Sondaki tarihi (YYYY-MM-DD) ayrıştır
        tarih_eslesmesi = re.search(r"(\d{4}-\d{2}-\d{2})\s*$", baslik)
        if tarih_eslesmesi:
            duyuru_tarihi = tarih_eslesmesi.group(1)
            baslik = baslik[:tarih_eslesmesi.start()].strip()
        else:
            duyuru_tarihi = None

        href = link_tag["href"]
        if not href.startswith("http"):
            href = "https://corlumyo.nku.edu.tr" + href

        duyurular.append({
            "baslik": baslik,
            "tarih": duyuru_tarihi,
            "url": href,
        })

    return duyurular, None


def staj_duyurularini_filtrele(duyurular: list) -> list:
    """
    Duyuru listesini filtreler: başlığında TÜM anahtar kelimeler geçen duyuruları döndürür.
    """
    eslesmeler = []
    for d in duyurular:
        baslik_kucuk = d["baslik"].lower()
        if all(k in baslik_kucuk for k in ANAHTAR_KELIMELER):
            eslesmeler.append(d)
    return eslesmeler


def siteyi_kontrol_et():
    """Ana kontrol fonksiyonu."""
    zaman = datetime.now(TZ_TURKEY).strftime("%Y-%m-%d %H:%M")
    print(f"[{zaman}] 🔍 Duyurular bölümü taranıyor...")

    duyurular, hata = duyurulari_cek()

    if duyurular is None:
        print(f"[{zaman}] ❌ Siteye erişilemedi: {hata}")
        telegram_gonder(
            f"⚠️ <b>Staj Takip Botu - Erişim Hatası</b>\n"
            f"🕐 {zaman}\n"
            f"Siteye erişilemedi: {hata}"
        )
        return

    print(f"[{zaman}] 📋 Toplam {len(duyurular)} duyuru bulundu.")

    staj_duyurulari = staj_duyurularini_filtrele(duyurular)

    if not staj_duyurulari:
        mesaj = (
            f"🔔 <b>Çorlu MYO Staj Takip Botu</b>\n"
            f"🕐 {zaman}\n\n"
            f"ℹ️ Yaz stajı duyurusu henüz yayınlanmamış.\n"
            f"Aranan kelimeler: <i>{', '.join(ANAHTAR_KELIMELER)}</i>\n"
            f"Taranan duyuru sayısı: {len(duyurular)}"
        )
        telegram_gonder(mesaj)
        print(f"[{zaman}] ℹ️ Yaz stajı duyurusu bulunamadı. ({len(duyurular)} duyuru tarandı)")
        return

    # Staj duyurusu/ları bulundu!
    for d in staj_duyurulari[:3]:
        baslik = d["baslik"]
        link = d["url"]
        tarih = d["tarih"] or "Belirtilmemiş"

        mesaj_satirlari = [
            f"🎓 <b>YAZ STAJI DUYURUSU YAYINLANDI!</b>",
            f"🕐 Kontrol zamanı: {zaman}",
            f"",
            f"📌 <b>Başlık:</b> {baslik[:200]}",
            f"📅 <b>Duyuru Tarihi:</b> {tarih}",
            f"🔗 <b>Link:</b> {link}",
            f"",
            f"⚠️ Detaylar için linke tıklayınız.",
        ]

        mesaj = "\n".join(mesaj_satirlari)
        telegram_gonder(mesaj)
        print(f"[{zaman}] 🎉 Staj duyurusu bulundu → {baslik[:60]}")


# ============================================================
#  Ana akış
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Çorlu MYO Staj Takip Botu")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Sadece bir kez çalıştır ve çık (test için)",
    )
    args = parser.parse_args()

    # Token kontrolü (henüz doldurulmamış placeholder kontrolü)
    if BOT_TOKEN == "BURAYA_BOT_TOKEN_YAZ" or CHAT_ID == "BURAYA_CHAT_ID_YAZ":
        print("❗ HATA: BOT_TOKEN ve CHAT_ID değerlerini scriptin içine girmeyi unutma!")
        return

    if args.once:
        print("🔄 Tek seferlik kontrol başlatılıyor...")
        siteyi_kontrol_et()
        return

    # Her gün 00:00'da çalıştır
    schedule.every().day.at("00:00").do(siteyi_kontrol_et)

    print("=" * 55)
    print("  Çorlu MYO Yaz Stajı Takip Botu başlatıldı")
    print(f"  Her gün 00:00'da kontrol edilecek")
    print(f"  Hedef: {TARGET_URL}")
    print(f"  Anahtar kelimeler: {', '.join(ANAHTAR_KELIMELER)}")
    print("  Durdurmak için: Ctrl+C")
    print("=" * 55)

    # Başlangıçta hemen bir kontrol yap
    print("🚀 Başlangıç kontrolü yapılıyor...")
    siteyi_kontrol_et()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
