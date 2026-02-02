import feedparser
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import re
from dotenv import load_dotenv
import markdown

# .env dosyasından şifreleri yükle
load_dotenv()

# RSS kaynakları
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://webrazzi.com/kategori/yapay-zeka/feed/"
]

def rss_haberlerini_topla():
    """RSS kaynaklarından son 7 günün haberlerini al"""
    tum_haberler = []
    yedi_gun_once = datetime.now() - timedelta(days=7)
    
    print("📡 RSS haberler toplanıyor...")
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for haber in feed.entries[:20]:  # Her kaynaktan max 20
                # Tarih kontrolü
                if hasattr(haber, 'published_parsed'):
                    yayın_tarihi = datetime(*haber.published_parsed[:6])
                    if yayın_tarihi < yedi_gun_once:
                        continue
                
                haber_bilgisi = {
                    'baslik': haber.title,
                    'link': haber.link,
                    'ozet': haber.get('summary', '')[:200],
                    'tarih': haber.get('published', '')
                }
                tum_haberler.append(haber_bilgisi)
        except Exception as hata:
            print(f"⚠️  RSS okuma hatası ({feed_url}): {hata}")
    
    print(f"✅ {len(tum_haberler)} haber toplandı")
    return tum_haberler

def gemini_ile_ozetle(haberler):
    """Gemini AI ile haberleri filtrele ve özetle"""
    print("🤖 Gemini AI ile özetleniyor...")
    
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Haberleri metin haline getir
    haber_metni = "\n\n".join([
        f"Başlık: {h['baslik']}\nLink: {h['link']}\nTarih: {h['tarih']}"
        for h in haberler
    ])
    
    prompt = f"""
Sen deneyimli bir teknoloji editörüsün ve haftalık bir AI haber bülteni hazırlıyorsun.

Aşağıdaki AI haberlerini incele ve SADECE gerçekten önemli, ilgi çekici ve değerli olanları seç. 
Kriterlerin:
- Önemli teknolojik gelişmeler (yeni model lansmanları, büyük güncellemeler)
- Sektöre etki eden haberler (şirket stratejileri, yatırımlar, düzenlemeler)
- İlginç uygulamalar ve kullanım senaryoları
- Tekrar eden veya önemsiz haberleri ATLAT
- haberleri en önemli gördüklerin üstte olacak şekilde sırala
- önemsiz gördüklerini de ayrıca bir özet rapor en alta ekle. bunlar için link verme, sadece bir kaç cümle ile gelişmeler hakkında bilgi ver.

HABER SAYISI SANA KALMIS - Önemli olan kalite.

Her haberi şu formatta sun:
- **Başlık (Türkçe ve çarpıcı)**
- Özet (2-3 cümle, Türkçe)
- Kaynak linki



HABERLER:
{haber_metni}
"""
    
    try:
        yanit = model.generate_content(prompt)
        print("✅ Özetleme tamamlandı")
        return yanit.text
    except Exception as hata:
        print(f"❌ Gemini hatası: {hata}")
        return None

def email_gonder(icerik):
    """Gmail ile e-posta gönder"""
    print("📧 E-posta gönderiliyor...")
    
    gonderen = os.getenv('GMAIL_ADDRESS')
    sifre = os.getenv('GMAIL_APP_PASSWORD')
    alici = os.getenv('ALICI_EMAIL', gonderen)  # Farklı adrese gönder
    
    if not icerik or not isinstance(icerik, str):
        icerik = ""
    
    # Gemini'nin Markdown çıktısını HTML'e çevir (başlıklar, linkler düzgün görünsün)
    try:
        icerik_html = markdown.markdown(icerik, extensions=['extra', 'nl2br'])
        # Düz yazılmış URL'leri tıklanabilir link yap (e-postada aktif olsun)
        icerik_html = re.sub(
            r'(\s)(https?://[^\s<"]+)(\s|<|$)',
            r'\1<a href="\2" style="color: #2563eb;" target="_blank" rel="noopener">\2</a>\3',
            icerik_html
        )
    except Exception:
        icerik_html = icerik.replace("\n", "<br>")
    
    mesaj = MIMEMultipart('alternative')
    mesaj['Subject'] = f"🤖 Haftalık AI Haber Bülteni - {datetime.now().strftime('%d %B %Y')}"
    mesaj['From'] = gonderen
    mesaj['To'] = alici
    
    html_icerik = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h1 style="color: #2563eb;">🤖 Bu Haftanın AI Haberleri</h1>
            <p style="color: #666;"><i>{datetime.now().strftime('%d %B %Y')} tarihli özet</i></p>
            <hr style="border: 1px solid #e5e7eb;">
            {icerik_html}
            <hr style="border: 1px solid #e5e7eb;">
            <p style="color: #999; font-size: 12px;">
                Bu e-posta Python scripti tarafından otomatik oluşturulmuştur.
            </p>
        </body>
    </html>
    """
    
    mesaj.attach(MIMEText(html_icerik, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gonderen, sifre)
            server.send_message(mesaj)
        print("✅ E-posta başarıyla gönderildi!")
        return True
    except Exception as hata:
        print(f"❌ E-posta hatası: {hata}")
        return False

def main():
    """Ana program"""
    print("\n" + "="*50)
    print("🚀 HAFTALIK AI HABER BÜLTENİ")
    print("="*50 + "\n")
    
    # 1. Haberleri topla
    haberler = rss_haberlerini_topla()
    
    if not haberler:
        print("❌ Haber bulunamadı, program sonlanıyor.")
        return
    
    # 2. Gemini ile özetle
    ozet = gemini_ile_ozetle(haberler)
    
    if not ozet:
        print("❌ Özetleme başarısız, program sonlanıyor.")
        return
    
    # 3. E-posta gönder
    basarili = email_gonder(ozet)
    
    if basarili:
        print("\n" + "="*50)
        print("✅ BÜLTEN BAŞARIYLA GÖNDERİLDİ!")
        print("="*50 + "\n")
    else:
        print("\n❌ İşlem tamamlanamadı.\n")

if __name__ == "__main__":
    main()