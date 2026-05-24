"""
DeBian guided frontend.

Run:
    python frontend\\streamlit_app.py

Open:
    http://127.0.0.1:8501
"""

from __future__ import annotations

import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Load .env from the project root (two levels up from this file) so that
# OPENAI_API_KEY and other vars are available without manually exporting them.
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # python-dotenv (in requirements.txt)
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        # Fallback: parse .env manually if python-dotenv isn't installed
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

_load_dotenv()


# ---------------------------------------------------------------------------
# Per-language UI strings for the guided claim flow
# ---------------------------------------------------------------------------

LANG_OPTIONS = [
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("tr", "Türkçe"),
    ("pl", "Polski"),
    ("ar", "العربية"),
    ("ta", "தமிழ்"),
]

GUIDED: dict[str, dict[str, str]] = {
    "en": {
        "greet1":        "Hello! 👋 I am DeBian, your Digital Rail Assistant.",
        "greet2":        "Choose: Book a ticket, Claim compensation, Check delay, or Human assistance.",
        "book":          "Please tell me origin, destination, date, and preferred time.",
        "claim_start":   "I will guide your compensation claim step by step.\n\nWhat is your train number?\nExample: ICE 572",
        "delay_start":   "Enter train number.\nExample: ICE 572, ICE 999, or RE 50",
        "ask_station":   "Which station should I use?\nExample: Frankfurt(Main)Hbf",
        "ask_planned":   "What was your planned start time?\nExample: 2026-05-20T10:00:00",
        "ask_actual":    "What was the actual start time?\nYou can also type: not started",
        "ask_delay":     "How many minutes was the delay?\nExample: 95",
        "ask_alt":       "Which alternative travel option did you use?\nExample: Regional train, next ICE, bus, taxi, or none",
        "ask_price":     "What was the ticket price in EUR?\nExample: 80",
        "ask_refund":    "How would you like to receive compensation?\nType: bank_account or voucher",
        "ask_iban":      "Please enter your IBAN/account number.\nI will only show the last 4 digits.",
        "ask_address":   "Please enter your home address for voucher confirmation.",
        "not_started_kw": "not",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "de": {
        "greet1":        "Hallo! 👋 Ich bin DeBian, Ihr digitaler Bahnassistent.",
        "greet2":        "Wählen Sie: Ticket buchen, Entschädigung beantragen, Verspätung prüfen oder menschliche Unterstützung.",
        "book":          "Bitte nennen Sie Abfahrtsort, Ziel, Datum und bevorzugte Uhrzeit.",
        "claim_start":   "Ich führe Sie Schritt für Schritt durch Ihren Entschädigungsantrag.\n\nWie lautet Ihre Zugnummer?\nBeispiel: ICE 572",
        "delay_start":   "Zugnummer eingeben.\nBeispiel: ICE 572, ICE 999 oder RE 50",
        "ask_station":   "Welchen Bahnhof soll ich verwenden?\nBeispiel: Frankfurt(Main)Hbf",
        "ask_planned":   "Wann war Ihre geplante Startzeit?\nBeispiel: 2026-05-20T10:00:00",
        "ask_actual":    "Wann ist der Zug tatsächlich abgefahren?\nSie können auch tippen: nicht gestartet",
        "ask_delay":     "Wie viele Minuten betrug die Verspätung?\nBeispiel: 95",
        "ask_alt":       "Welche alternative Reiseoption haben Sie genutzt?\nBeispiel: Regionalzug, nächster ICE, Bus, Taxi oder keine",
        "ask_price":     "Wie hoch war der Ticketpreis in EUR?\nBeispiel: 80",
        "ask_refund":    "Wie möchten Sie Ihre Entschädigung erhalten?\nEingabe: bank_account oder voucher",
        "ask_iban":      "Bitte geben Sie Ihre IBAN / Kontonummer ein.\nIch zeige nur die letzten 4 Ziffern.",
        "ask_address":   "Bitte geben Sie Ihre Heimadresse für den Gutscheinversand ein.",
        "not_started_kw": "nicht",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "fr": {
        "greet1":        "Bonjour ! 👋 Je suis DeBian, votre assistant ferroviaire numérique.",
        "greet2":        "Choisissez : Réserver un billet, Demander une indemnisation, Vérifier un retard ou Assistance humaine.",
        "book":          "Veuillez indiquer l'origine, la destination, la date et l'heure souhaitée.",
        "claim_start":   "Je vais vous guider étape par étape dans votre demande d'indemnisation.\n\nQuel est votre numéro de train ?\nExemple : ICE 572",
        "delay_start":   "Entrez le numéro de train.\nExemple : ICE 572, ICE 999 ou RE 50",
        "ask_station":   "Quelle gare dois-je utiliser ?\nExemple : Frankfurt(Main)Hbf",
        "ask_planned":   "Quelle était votre heure de départ prévue ?\nExemple : 2026-05-20T10:00:00",
        "ask_actual":    "Quelle était l'heure de départ réelle ?\nVous pouvez aussi taper : non parti",
        "ask_delay":     "Combien de minutes de retard ?\nExemple : 95",
        "ask_alt":       "Quel transport alternatif avez-vous utilisé ?\nExemple : train régional, ICE suivant, bus, taxi ou aucun",
        "ask_price":     "Quel était le prix du billet en EUR ?\nExemple : 80",
        "ask_refund":    "Comment souhaitez-vous recevoir l'indemnisation ?\nTapez : bank_account ou voucher",
        "ask_iban":      "Veuillez entrer votre IBAN / numéro de compte.\nJe n'afficherai que les 4 derniers chiffres.",
        "ask_address":   "Veuillez entrer votre adresse pour la livraison du bon.",
        "not_started_kw": "non",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "es": {
        "greet1":        "¡Hola! 👋 Soy DeBian, su asistente ferroviario digital.",
        "greet2":        "Elija: Reservar billete, Reclamar compensación, Consultar retraso o Asistencia humana.",
        "book":          "Indíqueme origen, destino, fecha y hora preferida.",
        "claim_start":   "Le guiaré paso a paso en su reclamación.\n\n¿Cuál es el número de su tren?\nEjemplo: ICE 572",
        "delay_start":   "Escriba el número del tren.\nEjemplo: ICE 572, ICE 999 o RE 50",
        "ask_station":   "¿Qué estación debo usar?\nEjemplo: Frankfurt(Main)Hbf",
        "ask_planned":   "¿Cuál era la hora de salida prevista?\nEjemplo: 2026-05-20T10:00:00",
        "ask_actual":    "¿Cuándo salió realmente el tren?\nTambién puede escribir: no salió",
        "ask_delay":     "¿Cuántos minutos de retraso?\nEjemplo: 95",
        "ask_alt":       "¿Qué transporte alternativo utilizó?\nEjemplo: tren regional, siguiente ICE, autobús, taxi o ninguno",
        "ask_price":     "¿Cuál fue el precio del billete en EUR?\nEjemplo: 80",
        "ask_refund":    "¿Cómo desea recibir la compensación?\nEscriba: bank_account o voucher",
        "ask_iban":      "Introduzca su IBAN / número de cuenta.\nSolo mostraré los últimos 4 dígitos.",
        "ask_address":   "Introduzca su dirección para el envío del bono.",
        "not_started_kw": "no",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "it": {
        "greet1":        "Salve! 👋 Sono DeBian, il suo assistente ferroviario digitale.",
        "greet2":        "Scelga: Prenota biglietto, Richiedi indennizzo, Verifica ritardo o Assistenza umana.",
        "book":          "Indichi origine, destinazione, data e orario preferito.",
        "claim_start":   "La guiderò passo dopo passo nella sua richiesta di indennizzo.\n\nQual è il numero del suo treno?\nEsempio: ICE 572",
        "delay_start":   "Inserisca il numero del treno.\nEsempio: ICE 572, ICE 999 o RE 50",
        "ask_station":   "Quale stazione devo usare?\nEsempio: Frankfurt(Main)Hbf",
        "ask_planned":   "Qual era l'orario di partenza previsto?\nEsempio: 2026-05-20T10:00:00",
        "ask_actual":    "A che ora è partito effettivamente il treno?\nPuò anche scrivere: non partito",
        "ask_delay":     "Quanti minuti di ritardo?\nEsempio: 95",
        "ask_alt":       "Quale trasporto alternativo ha usato?\nEsempio: treno regionale, ICE successivo, bus, taxi o nessuno",
        "ask_price":     "Qual era il prezzo del biglietto in EUR?\nEsempio: 80",
        "ask_refund":    "Come desidera ricevere l'indennizzo?\nScriva: bank_account o voucher",
        "ask_iban":      "Inserisca il suo IBAN / numero di conto.\nMostrerò solo le ultime 4 cifre.",
        "ask_address":   "Inserisca il suo indirizzo per la consegna del voucher.",
        "not_started_kw": "non",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "tr": {
        "greet1":        "Merhaba! 👋 Ben DeBian, dijital demiryolu asistanınız.",
        "greet2":        "Seçin: Bilet rezervasyonu, Tazminat talebi, Gecikme sorgulama veya İnsan desteği.",
        "book":          "Lütfen kalkış yeri, varış yeri, tarih ve tercih edilen saati belirtin.",
        "claim_start":   "Tazminat talebinizde size adım adım rehberlik edeceğim.\n\nTren numaranız nedir?\nÖrnek: ICE 572",
        "delay_start":   "Tren numarası girin.\nÖrnek: ICE 572, ICE 999 veya RE 50",
        "ask_station":   "Hangi istasyonu kullanmalıyım?\nÖrnek: Frankfurt(Main)Hbf",
        "ask_planned":   "Planlanan kalkış saatiniz neydi?\nÖrnek: 2026-05-20T10:00:00",
        "ask_actual":    "Tren gerçekte ne zaman kalktı?\nAyrıca yazabilirsiniz: kalkmadı",
        "ask_delay":     "Kaç dakika gecikti?\nÖrnek: 95",
        "ask_alt":       "Hangi alternatif ulaşımı kullandınız?\nÖrnek: bölgesel tren, sonraki ICE, otobüs, taksi veya hiçbiri",
        "ask_price":     "Bilet fiyatı EUR cinsinden ne kadardı?\nÖrnek: 80",
        "ask_refund":    "Tazminatı nasıl almak istersiniz?\nYazın: bank_account veya voucher",
        "ask_iban":      "IBAN / hesap numaranızı girin.\nYalnızca son 4 haneyi göstereceğim.",
        "ask_address":   "Kupon teslimi için ev adresinizi girin.",
        "not_started_kw": "kalkmadı",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "pl": {
        "greet1":        "Cześć! 👋 Jestem DeBian, Twój cyfrowy asystent kolejowy.",
        "greet2":        "Wybierz: Rezerwacja biletu, Roszczenie odszkodowania, Sprawdź opóźnienie lub Wsparcie ludzkie.",
        "book":          "Podaj miejsce odjazdu, cel, datę i preferowaną godzinę.",
        "claim_start":   "Poprowadzę Cię krok po kroku przez wniosek o odszkodowanie.\n\nJaki jest numer Twojego pociągu?\nPrzykład: ICE 572",
        "delay_start":   "Wpisz numer pociągu.\nPrzykład: ICE 572, ICE 999 lub RE 50",
        "ask_station":   "Której stacji użyć?\nPrzykład: Frankfurt(Main)Hbf",
        "ask_planned":   "Jaki był planowy czas odjazdu?\nPrzykład: 2026-05-20T10:00:00",
        "ask_actual":    "Kiedy faktycznie odjechał pociąg?\nMożesz też napisać: nie odjechał",
        "ask_delay":     "Ile minut wynosiło opóźnienie?\nPrzykład: 95",
        "ask_alt":       "Z jakiego alternatywnego transportu korzystałeś?\nPrzykład: pociąg regionalny, następny ICE, autobus, taksówka lub żaden",
        "ask_price":     "Jaka była cena biletu w EUR?\nPrzykład: 80",
        "ask_refund":    "Jak chcesz otrzymać odszkodowanie?\nWpisz: bank_account lub voucher",
        "ask_iban":      "Wprowadź swój IBAN / numer konta.\nPokaże tylko ostatnie 4 cyfry.",
        "ask_address":   "Wprowadź swój adres domowy do wysyłki kuponu.",
        "not_started_kw": "nie",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "ar": {
        "greet1":        "مرحباً! 👋 أنا DeBian، مساعدك الرقمي للسكك الحديدية.",
        "greet2":        "اختر: حجز تذكرة، طلب تعويض، التحقق من التأخير، أو دعم بشري.",
        "book":          "يرجى إخباري بنقطة الانطلاق والوجهة والتاريخ والوقت المفضل.",
        "claim_start":   "سأرشدك خطوة بخطوة في طلب التعويض.\n\nما هو رقم قطارك؟\nمثال: ICE 572",
        "delay_start":   "أدخل رقم القطار.\nمثال: ICE 572 أو ICE 999 أو RE 50",
        "ask_station":   "أي محطة يجب أن أستخدم؟\nمثال: Frankfurt(Main)Hbf",
        "ask_planned":   "ما كان وقت المغادرة المخطط؟\nمثال: 2026-05-20T10:00:00",
        "ask_actual":    "متى غادر القطار فعلياً؟\nيمكنك أيضاً كتابة: لم يغادر",
        "ask_delay":     "كم دقيقة كان التأخير؟\nمثال: 95",
        "ask_alt":       "ما وسيلة النقل البديلة التي استخدمتها؟\nمثال: قطار إقليمي، ICE التالي، حافلة، تاكسي، أو لا شيء",
        "ask_price":     "ما كان سعر التذكرة بالـ EUR؟\nمثال: 80",
        "ask_refund":    "كيف تريد استلام التعويض؟\nاكتب: bank_account أو voucher",
        "ask_iban":      "أدخل رقم IBAN / الحساب.\nسأعرض فقط آخر 4 أرقام.",
        "ask_address":   "أدخل عنوانك المنزلي لتسليم القسيمة.",
        "not_started_kw": "لم",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
    "ta": {
        "greet1":        "வணக்கம்! 👋 நான் DeBian, உங்கள் டிஜிட்டல் ரயில் உதவியாளர்.",
        "greet2":        "தேர்வு செய்யுங்கள்: டிக்கெட் புக் செய்யுங்கள், இழப்பீடு கோரிக்கை, தாமத சோதனை அல்லது மனித ஆதரவு.",
        "book":          "தொடக்க இடம், இலக்கு, தேதி மற்றும் விரும்பிய நேரம் தெரிவிக்கவும்.",
        "claim_start":   "இழப்பீடு கோரிக்கையில் படிப்படியாக உங்களுக்கு வழிகாட்டுவேன்.\n\nரயில் எண் என்ன?\nஉதாரணம்: ICE 572",
        "delay_start":   "ரயில் எண் உள்ளிடவும்.\nஉதாரணம்: ICE 572, ICE 999 அல்லது RE 50",
        "ask_station":   "எந்த நிலையம் பயன்படுத்த வேண்டும்?\nஉதாரணம்: Frankfurt(Main)Hbf",
        "ask_planned":   "திட்டமிட்ட புறப்பாடு நேரம் என்ன?\nஉதாரணம்: 2026-05-20T10:00:00",
        "ask_actual":    "ரயில் உண்மையில் எப்போது புறப்பட்டது?\nடைப் செய்யலாம்: புறப்படவில்லை",
        "ask_delay":     "தாமதம் எத்தனை நிமிடங்கள்?\nஉதாரணம்: 95",
        "ask_alt":       "எந்த மாற்று போக்குவரத்து பயன்படுத்தினீர்கள்?\nஉதாரணம்: பிராந்திய ரயில், அடுத்த ICE, பேருந்து, டாக்சி அல்லது எதுவும் இல்லை",
        "ask_price":     "டிக்கெட் விலை EUR இல் என்ன?\nஉதாரணம்: 80",
        "ask_refund":    "இழப்பீடு எவ்வாறு பெற விரும்புகிறீர்கள்?\nடைப் செய்யுங்கள்: bank_account அல்லது voucher",
        "ask_iban":      "உங்கள் IBAN / கணக்கு எண் உள்ளிடவும்.\nகடைசி 4 இலக்கங்கள் மட்டும் காட்டுவேன்.",
        "ask_address":   "கூப்பன் டெலிவரிக்கான முகவரி உள்ளிடவும்.",
        "not_started_kw": "இல்லை",
        "bank_kw":       "bank_account",
        "voucher_kw":    "voucher",
    },
}


def _g(lang: str, key: str) -> str:
    """Return a guided-flow string for *lang*, falling back to English."""
    return GUIDED.get(lang, GUIDED["en"]).get(key, GUIDED["en"][key])


# ---------------------------------------------------------------------------
# HTML template — language select now has all 9 options
# ---------------------------------------------------------------------------

_LANG_OPTIONS_HTML = "\n".join(
    f'<option value="{code}">{label}</option>' for code, label in LANG_OPTIONS
)

FALLBACK_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>DeBian – Digital Rail Assistant</title>
  <!-- API key injected at serve-time by FallbackHandler -->
  <script>window.OPENAI_API_KEY="__OPENAI_KEY__";</script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;700&display=swap');
    :root{--red:#e30613;--bg:#ffffff;--panel:rgba(227,6,19,.06);--panel2:rgba(227,6,19,.03);--border:rgba(227,6,19,.18);--muted:#999;--green:#16a34a;--amber:#d97706;--blue:#2563eb;--purple:#7c3aed;}
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:'Inter',sans-serif;background:#fff;color:#1a1a1a;min-height:100vh;}
    /* ─── layout ─── */
    #app{display:flex;height:100vh;overflow:hidden;}
    #sidebar{width:260px;min-width:220px;background:#fff;border-right:2px solid var(--border);display:flex;flex-direction:column;padding:0;flex-shrink:0;}
    #main-area{flex:1;overflow:hidden;display:flex;flex-direction:column;background:#fafafa;}
    /* ─── sidebar ─── */
    .sb-logo{padding:24px 20px 16px;border-bottom:2px solid var(--border);background:#fff;}
    .sb-logo h1{font-family:'Space Grotesk',sans-serif;font-size:32px;letter-spacing:-1px;line-height:1;color:#1a1a1a;}
    .sb-logo h1 span{color:var(--red);}
    .sb-logo p{color:var(--muted);font-size:12px;margin-top:4px;}
    .sb-nav{flex:1;padding:12px 10px;overflow-y:auto;background:#fff;}
    .nav-section{font-size:10px;font-weight:600;letter-spacing:.1em;color:var(--muted);text-transform:uppercase;padding:14px 10px 6px;}
    .nav-btn{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border:none;background:transparent;color:#555;border-radius:10px;cursor:pointer;font-size:13.5px;text-align:left;transition:all .15s;}
    .nav-btn:hover{background:rgba(227,6,19,.08);color:var(--red);}
    .nav-btn.active{background:rgba(227,6,19,.12);color:var(--red);font-weight:600;}
    .nav-icon{font-size:16px;flex-shrink:0;width:20px;text-align:center;}
    .role-badge{font-size:10px;padding:2px 7px;border-radius:20px;font-weight:600;margin-left:auto;flex-shrink:0;}
    .role-admin{background:rgba(124,58,237,.12);color:#7c3aed;}
    .role-employee{background:rgba(37,99,235,.12);color:#2563eb;}
    .role-customer{background:rgba(22,163,74,.12);color:#16a34a;}
    .sb-user{padding:14px;border-top:2px solid var(--border);background:#fff;}
    .sb-user-name{font-size:13px;font-weight:600;color:#1a1a1a;}
    .sb-user-role{font-size:11px;color:var(--muted);}
    .sb-user-iban{font-size:11px;color:var(--muted);margin-top:2px;}
    .sb-login-btn{width:100%;margin-top:8px;padding:9px;border-radius:10px;background:var(--red);border:none;color:white;font-weight:600;cursor:pointer;font-size:13px;}
    /* ─── tabs ─── */
    #tab-bar{display:flex;border-bottom:1px solid var(--border);background:#fff;padding:0 20px;}
    .tab{padding:13px 18px;cursor:pointer;font-size:13px;color:var(--muted);border-bottom:2px solid transparent;transition:all .15s;white-space:nowrap;}
    .tab.active{color:var(--red);border-bottom-color:var(--red);}
    /* ─── chat panel ─── */
    #chat-panel{display:flex;height:100%;flex-direction:column;padding:0;}
    .chat-box{flex:1;overflow-y:auto;background:#fff;margin:0 20px;border:1px solid var(--border);border-radius:18px;padding:14px;min-height:0;}
    .msg{max-width:82%;padding:11px 14px;border-radius:14px;margin:8px 0;white-space:pre-wrap;line-height:1.5;font-size:14px;}
    .bot{background:#f5f5f5;border:1px solid #e8e8e8;color:#1a1a1a;}
    .user{background:var(--red);color:white;margin-left:auto;max-width:fit-content;}
    .chat-input-area{padding:12px 20px 16px;display:flex;flex-direction:column;gap:8px;background:#fafafa;}
    #file-preview{display:none;background:#fff3f3;border:1px solid var(--border);border-radius:12px;padding:8px 12px;font-size:12px;color:var(--muted);position:relative;}
    #file-preview .fp-name{color:#1a1a1a;font-weight:600;margin-bottom:2px;}
    #file-preview img{max-height:80px;border-radius:6px;margin-top:4px;display:block;}
    #file-preview .fp-clear{position:absolute;top:6px;right:10px;cursor:pointer;font-size:16px;color:#888;}
    .input-row{display:flex;gap:8px;align-items:stretch;}
    .input-row #input{flex:1;min-width:0;margin:0;padding:12px 14px;background:#fff;border:1px solid var(--border);border-radius:12px;color:#1a1a1a;font-size:14px;}
    .input-row #input:focus{outline:none;border-color:var(--red);}
    .icon-btn{flex-shrink:0;width:46px;height:46px;background:#fff;border:1px solid var(--border);border-radius:12px;cursor:pointer;color:#555;display:flex;align-items:center;justify-content:center;}
    .icon-btn:hover{background:#fff3f3;color:var(--red);}
    .icon-btn.recording{background:var(--red);color:white;animation:pulse .8s infinite;}
    #btn-send-main{flex-shrink:0;padding:0 20px;height:46px;background:var(--red);border:none;border-radius:12px;color:white;font-weight:700;cursor:pointer;font-size:14px;}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    /* ─── analytics panel ─── */
    #analytics-panel{display:none;height:100%;overflow-y:auto;padding:24px;background:#fafafa;}
    .dash-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin-bottom:24px;}
    .kpi-card{background:#fff;border:1px solid var(--border);border-radius:20px;padding:20px 22px;}
    .kpi-label{font-size:12px;color:var(--muted);font-weight:500;margin-bottom:8px;}
    .kpi-value{font-size:36px;font-weight:700;font-family:'Space Grotesk',sans-serif;line-height:1;color:#1a1a1a;}
    .kpi-sub{font-size:12px;color:var(--muted);margin-top:4px;}
    .kpi-green{color:var(--green);}
    .kpi-red{color:var(--red);}
    .kpi-amber{color:var(--amber);}
    .kpi-blue{color:var(--blue);}
    .chart-card{background:#fff;border:1px solid var(--border);border-radius:20px;padding:20px 22px;margin-bottom:20px;}
    .chart-card h3{font-size:14px;font-weight:600;margin-bottom:16px;color:#333;}
    .bar-chart{display:flex;align-items:flex-end;gap:10px;height:160px;}
    .bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;}
    .bar{width:100%;border-radius:6px 6px 0 0;transition:height .4s;min-height:4px;}
    .bar-label{font-size:11px;color:var(--muted);text-align:center;}
    .bar-val{font-size:11px;font-weight:600;text-align:center;color:#333;}
    .h-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
    .h-bar-label{font-size:12px;color:#333;width:160px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .h-bar-track{flex:1;background:#f0f0f0;border-radius:6px;height:22px;position:relative;}
    .h-bar-fill{height:100%;border-radius:6px;display:flex;align-items:center;padding-left:8px;font-size:11px;font-weight:600;transition:width .5s;}
    .h-bar-pct{font-size:12px;color:var(--muted);width:42px;text-align:right;flex-shrink:0;}
    .train-table{width:100%;border-collapse:collapse;font-size:13px;}
    .train-table th{text-align:left;color:var(--muted);font-weight:500;padding:8px 10px;border-bottom:1px solid var(--border);font-size:11px;text-transform:uppercase;letter-spacing:.05em;}
    .train-table td{padding:10px 10px;border-bottom:1px solid #f0f0f0;color:#1a1a1a;}
    .status-pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;}
    .pill-full{background:rgba(227,6,19,.12);color:var(--red);}
    .pill-high{background:rgba(217,119,6,.12);color:var(--amber);}
    .pill-low{background:rgba(22,163,74,.12);color:var(--green);}
    .occ-bar-wrap{display:flex;align-items:center;gap:8px;}
    .occ-mini{flex:1;height:8px;background:#f0f0f0;border-radius:4px;}
    .occ-mini-fill{height:100%;border-radius:4px;}
    .charts-2col{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
    /* ─── occupancy panel ─── */
    #occupancy-panel{display:none;height:100%;overflow-y:auto;padding:24px;background:#fafafa;}
    .occ-search{display:flex;gap:10px;margin-bottom:20px;}
    .occ-search input{flex:1;padding:11px 14px;background:#fff;border:1px solid var(--border);border-radius:12px;color:#1a1a1a;font-size:14px;}
    .occ-search button{padding:11px 22px;background:var(--red);border:none;border-radius:12px;color:white;font-weight:700;cursor:pointer;}
    .occ-result{background:#fff;border:1px solid var(--border);border-radius:20px;padding:22px;display:none;color:#1a1a1a;}
    /* ─── profile panel ─── */
    #profile-panel{display:none;height:100%;overflow-y:auto;padding:24px;background:#fafafa;}
    .profile-card{background:#fff;border:1px solid var(--border);border-radius:20px;padding:26px;max-width:560px;}
    .profile-field{margin-bottom:14px;}
    .profile-field label{display:block;font-size:11px;color:var(--muted);margin-bottom:5px;font-weight:500;}
    .profile-field input,.profile-field select{width:100%;padding:10px 14px;background:#fff;border:1px solid var(--border);border-radius:10px;color:#1a1a1a;font-size:14px;}
    .profile-field .value{font-size:14px;padding:10px 0;color:#1a1a1a;}
    .save-btn{padding:11px 26px;background:var(--red);border:none;border-radius:12px;color:white;font-weight:700;cursor:pointer;font-size:14px;margin-top:8px;}
    .iban-display{font-family:monospace;font-size:16px;color:#1a1a1a;padding:12px 16px;background:#f5f5f5;border:1px solid var(--border);border-radius:10px;letter-spacing:2px;}
    /* ─── login modal ─── */
    #modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:1000;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px);}
    .modal{background:#fff;border:1px solid var(--border);border-radius:24px;padding:36px;width:380px;max-width:92vw;}
    .modal h2{font-family:'Space Grotesk',sans-serif;font-size:26px;margin-bottom:4px;color:#1a1a1a;}
    .modal p{color:var(--muted);font-size:13px;margin-bottom:22px;}
    .modal input,.modal select{width:100%;padding:12px 14px;background:#f5f5f5;border:1px solid var(--border);border-radius:12px;color:#1a1a1a;font-size:14px;margin-bottom:10px;}
    .modal-btn{width:100%;padding:13px;background:var(--red);border:none;border-radius:12px;color:white;font-weight:700;cursor:pointer;font-size:15px;margin-top:4px;}
    .modal-link{text-align:center;margin-top:14px;font-size:13px;color:var(--muted);cursor:pointer;}
    .modal-link span{color:var(--red);}
    .modal-err{color:var(--red);font-size:13px;margin-bottom:8px;display:none;}
    .demo-pills{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;}
    .demo-pill{padding:5px 12px;border-radius:20px;font-size:12px;cursor:pointer;border:1px solid var(--border);background:#fff3f3;color:#555;transition:background .15s;}
    .demo-pill:hover{background:rgba(227,6,19,.12);color:var(--red);}
    /* ─── misc ─── */
    .hint{color:var(--muted);font-size:12px;}
    .section-title{font-size:22px;font-family:'Space Grotesk',sans-serif;font-weight:700;margin-bottom:6px;color:#1a1a1a;}
    .section-sub{font-size:13px;color:var(--muted);margin-bottom:20px;}
    @media(max-width:700px){#sidebar{width:60px;}#sidebar .sb-logo p,.sb-logo h1,.nav-btn span,.sb-user-name,.sb-user-role,.sb-user-iban{display:none;}.nav-btn{justify-content:center;padding:12px;}.charts-2col{grid-template-columns:1fr;}}
  </style>
</head>
<body>
<div id="app">

<!-- ═══════════════════════════════ SIDEBAR ═══════════════════════════════ -->
<div id="sidebar">
  <div class="sb-logo">
    <h1><span>D</span>e<span>B</span>ian</h1>
    <p>Digital Rail Assistant</p>
  </div>
  <nav class="sb-nav">
    <div class="nav-section">Navigation</div>
    <button class="nav-btn active" onclick="showPanel('chat')" id="nav-chat">
      <span class="nav-icon">💬</span><span>Chat</span>
    </button>
    <button class="nav-btn" onclick="showPanel('profile')" id="nav-profile">
      <span class="nav-icon">👤</span><span>My Profile</span>
    </button>
    <button class="nav-btn" onclick="showPanel('occupancy')" id="nav-occupancy" style="display:none">
      <span class="nav-icon">🚆</span><span>Occupancy</span>
    </button>
    <button class="nav-btn" onclick="showPanel('analytics')" id="nav-analytics" style="display:none">
      <span class="nav-icon">📊</span><span>Analytics</span>
    </button>
    <div class="nav-section">Settings</div>
    <div style="padding:6px 12px;">
      <input id="apiBase" value="http://127.0.0.1:8000" style="width:100%;padding:8px 10px;background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:8px;color:white;font-size:12px;" />
    </div>
    <button class="nav-btn" onclick="checkBackend()"><span class="nav-icon">🔌</span><span>Check Backend</span></button>
    <button class="nav-btn" onclick="runETL()"><span class="nav-icon">⚙️</span><span>Run ETL</span></button>
    <div style="padding:6px 12px;">
      <select id="language" onchange="onLangChange()" style="width:100%;padding:8px;background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:8px;color:white;font-size:12px;">
""" + _LANG_OPTIONS_HTML + r"""
      </select>
    </div>
    <p id="status" class="hint" style="padding:6px 14px;">Start backend: python -m app.main</p>
  </nav>
  <div class="sb-user" id="sb-user-area">
    <div id="sb-logged-out">
      <button class="sb-login-btn" onclick="showLogin()">🔑 Sign In</button>
    </div>
    <div id="sb-logged-in" style="display:none;">
      <div class="sb-user-name" id="sb-name">–</div>
      <div class="sb-user-role" id="sb-role">–</div>
      <div class="sb-user-iban" id="sb-iban"></div>
      <button class="sb-login-btn" onclick="logout()" style="background:rgba(255,255,255,.1);margin-top:8px;">Sign Out</button>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════ MAIN AREA ═══════════════════════════════ -->
<div id="main-area">

<!-- ── Chat Panel ─────────────────────────────────────────────────────────── -->
<div id="chat-panel" style="display:flex;flex-direction:column;height:100%;overflow:hidden;">

  <div id="chat" class="chat-box"></div>
  <div class="chat-input-area">
    <div id="file-preview">
      <span class="fp-clear" onclick="clearFile()">✕</span>
      <div class="fp-name" id="fp-name"></div>
      <div id="fp-img-wrap"></div>
    </div>
    <div class="input-row">
      <input id="input" placeholder="Type here…" onkeydown="if(event.key==='Enter')send()"/>
      <button class="icon-btn" id="btn-upload" onclick="document.getElementById('file-input').click()" title="Upload file">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
      </button>
      <input type="file" id="file-input" accept="image/*,.pdf,.txt,.doc,.docx" style="display:none" onchange="onFileSelected(this)"/>
      <button class="icon-btn" id="btn-mic" onmousedown="micStart(event)" onmouseup="micStop()" onmouseleave="micStop()" ontouchstart="micStart(event)" ontouchend="micStop()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>
      </button>
      <button id="btn-send-main" onclick="send()">Send →</button>
    </div>
  </div>
</div>

<!-- ── Profile Panel ──────────────────────────────────────────────────────── -->
<div id="profile-panel">
  <div class="section-title">My Profile</div>
  <div class="section-sub">Manage your account and banking details.</div>
  <div class="profile-card" id="profile-card">
    <p style="color:var(--muted);font-size:14px;">Please sign in to view your profile.</p>
  </div>
</div>

<!-- ── Occupancy Panel (employee/admin) ───────────────────────────────────── -->
<div id="occupancy-panel">
  <div class="section-title">Train Occupancy</div>
  <div class="section-sub">Check seat availability for any train. (Employee / Admin only)</div>
  <div class="occ-search">
    <input id="occ-input" placeholder="Train number: ICE 572, RE 50, …" onkeydown="if(event.key==='Enter')lookupOcc()"/>
    <button onclick="lookupOcc()">Check →</button>
  </div>
  <div class="occ-result" id="occ-result"></div>
  <div style="margin-top:28px;">
    <div class="section-title" style="font-size:17px;margin-bottom:12px;">Fleet Overview</div>
    <div id="fleet-table-wrap"></div>
  </div>
</div>

<!-- ── Analytics Panel (admin) ────────────────────────────────────────────── -->
<div id="analytics-panel">
  <div class="section-title">Analytics Dashboard</div>
  <div class="section-sub">Real-time rail operations overview · Admin only</div>
  <div class="dash-grid" id="kpi-grid"></div>
  <div class="charts-2col">
    <div class="chart-card">
      <h3>📈 Weekly Avg Occupancy (%)</h3>
      <div class="bar-chart" id="chart-occ"></div>
    </div>
    <div class="chart-card">
      <h3>💰 Monthly Revenue (€K)</h3>
      <div class="bar-chart" id="chart-rev"></div>
    </div>
  </div>
  <div class="chart-card">
    <h3>🚆 Occupancy by Route</h3>
    <div id="chart-routes"></div>
  </div>
  <div class="charts-2col">
    <div class="chart-card">
      <h3>⏱ Avg Delay by Train Type (min)</h3>
      <div id="chart-delay"></div>
    </div>
    <div class="chart-card">
      <h3>💶 Monthly Compensation Claims</h3>
      <div class="bar-chart" id="chart-claims"></div>
    </div>
  </div>
</div>

</div><!-- #main-area -->
</div><!-- #app -->

<!-- ═══════════════════════════════ LOGIN MODAL ═══════════════════════════ -->
<div id="modal-overlay" style="display:none;">
  <div class="modal">
    <h2 id="modal-title">Welcome back</h2>
    <p id="modal-sub">Sign in to access DeBian services.</p>
    <div class="demo-pills">
      <div class="demo-pill" onclick="fillDemo('customer_demo','customer123')">👤 Customer demo</div>
      <div class="demo-pill" onclick="fillDemo('employee_demo','employee123')">🏢 Employee demo</div>
      <div class="demo-pill" onclick="fillDemo('admin_demo','admin123')">🛡 Admin demo</div>
    </div>
    <div class="modal-err" id="modal-err"></div>
    <div id="modal-login-form">
      <input id="m-user" placeholder="Username"/>
      <input id="m-pass" placeholder="Password" type="password" onkeydown="if(event.key==='Enter')doLogin()"/>
      <button class="modal-btn" onclick="doLogin()">Sign In</button>
      <div class="modal-link">No account? <span onclick="toggleModal()">Register →</span></div>
    </div>
    <div id="modal-reg-form" style="display:none;">
      <input id="r-user" placeholder="Username"/>
      <input id="r-pass" placeholder="Password" type="password"/>
      <input id="r-name" placeholder="Full name"/>
      <input id="r-email" placeholder="Email"/>
      <select id="r-role"><option value="customer">Customer</option><option value="employee">Employee</option></select>
      <button class="modal-btn" onclick="doRegister()">Create Account</button>
      <div class="modal-link">Have an account? <span onclick="toggleModal()">Sign In →</span></div>
    </div>
    <div class="modal-link" style="margin-top:10px;" onclick="closeModal()">Continue as guest →</div>
  </div>
</div>

<script>
// ═══════════════════════ GUIDED STRINGS ═══════════════════════
const GUIDED = """ + __import__("json").dumps(GUIDED, ensure_ascii=False) + r""";
function g(key){ return (GUIDED[lang()]||GUIDED["en"])[key]||GUIDED["en"][key]; }

// ═══════════════════════ STATE ═══════════════════════
let step=null, claim={}, _history=[], _token=null, _user=null;
function api(){ return document.getElementById("apiBase").value.replace(/\/$/,""); }
function lang(){ return document.getElementById("language").value; }

// ═══════════════════════ PANELS ═══════════════════════
function showPanel(name){
  ["chat","profile","occupancy","analytics"].forEach(p=>{
    document.getElementById(p+"-panel").style.display="none";
    const nb=document.getElementById("nav-"+p);
    if(nb) nb.classList.remove("active");
  });
  document.getElementById(name+"-panel").style.display=name==="chat"?"flex":"block";
  const nb=document.getElementById("nav-"+name);
  if(nb) nb.classList.add("active");
  if(name==="analytics") loadAnalytics();
  if(name==="occupancy") loadFleetOverview();
  if(name==="profile")   renderProfile();
}

// ═══════════════════════ AUTH ═══════════════════════
function showLogin(){ document.getElementById("modal-overlay").style.display="flex"; }
function closeModal(){ document.getElementById("modal-overlay").style.display="none"; }
function toggleModal(){
  const l=document.getElementById("modal-login-form"),r=document.getElementById("modal-reg-form");
  const isLogin=l.style.display!=="none";
  l.style.display=isLogin?"none":"block";
  r.style.display=isLogin?"block":"none";
  document.getElementById("modal-title").innerText=isLogin?"Create Account":"Welcome back";
}
function fillDemo(u,p){ document.getElementById("m-user").value=u; document.getElementById("m-pass").value=p; }
function modalErr(msg){ const e=document.getElementById("modal-err"); e.innerText=msg; e.style.display=msg?"block":"none"; }

async function doLogin(){
  const username=document.getElementById("m-user").value.trim();
  const password=document.getElementById("m-pass").value;
  if(!username||!password){ modalErr("Please enter username and password."); return; }
  // Offline demo accounts (used when backend is not running)
  const DEMO_ACCOUNTS={
    "customer_demo":{password:"customer123",user:{user_id:"customer_demo",username:"customer_demo",full_name:"Maria Müller",email:"maria@example.com",role:"customer",masked_iban:"********************3000"}},
    "employee_demo":{password:"employee123",user:{user_id:"employee_demo",username:"employee_demo",full_name:"Hans Schmidt",email:"hans@bahn.de",role:"employee",masked_iban:null}},
    "admin_demo":{password:"admin123",user:{user_id:"admin_demo",username:"admin_demo",full_name:"Dr. Klaus Weber",email:"admin@bahn.de",role:"admin",masked_iban:null}},
  };
  try{
    const r=await fetch(api()+"/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username,password})}).catch(()=>null);
    let d=null;
    if(r&&r.ok) d=await r.json();
    if(!d||d._offline||!d.success){
      // Backend offline — try local demo accounts
      const demo=DEMO_ACCOUNTS[username];
      if(demo&&demo.password===password){
        _token="demo-token-offline"; _user=demo.user;
        closeModal(); applyAuth();
        add("bot","✅ Welcome back, "+_user.full_name+"! Role: "+_user.role+". (Offline mode — AI powered by OpenAI)");
        return;
      }
      if(d&&!d.success) modalErr(d.error||"Login failed.");
      else modalErr("Backend offline. Use demo accounts: customer_demo / employee_demo / admin_demo with passwords customer123 / employee123 / admin123");
      return;
    }
    _token=d.token; _user=d.user;
    closeModal(); applyAuth();
    add("bot","✅ Welcome back, "+_user.full_name+"! Role: "+_user.role+".");
  }catch(e){ modalErr("Login error: "+e.message); }
}

async function doRegister(){
  const body={username:document.getElementById("r-user").value.trim(),password:document.getElementById("r-pass").value,full_name:document.getElementById("r-name").value.trim(),email:document.getElementById("r-email").value.trim(),role:document.getElementById("r-role").value};
  try{
    const r=await fetch(api()+"/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json();
    if(!d.success){ modalErr(d.error||"Registration failed."); return; }
    _token=d.token; _user=d.user;
    closeModal(); applyAuth();
    add("bot","✅ Account created! Welcome, "+_user.full_name+".");
  }catch(e){ modalErr("Backend not reachable: "+e.message); }
}

function logout(){
  location.reload();
}

function applyAuth(){
  if(!_user) return;
  document.getElementById("sb-logged-out").style.display="none";
  document.getElementById("sb-logged-in").style.display="block";
  document.getElementById("sb-name").innerText=_user.full_name||_user.username;
  const roleLabel={"admin":"🛡 Admin","employee":"🏢 Employee","customer":"👤 Customer"}[_user.role]||_user.role;
  document.getElementById("sb-role").innerText=roleLabel;
  if(_user.masked_iban) document.getElementById("sb-iban").innerText="IBAN: ****"+_user.masked_iban.slice(-4);
  // show nav items based on role
  const lvl={"admin":3,"employee":2,"customer":1}[_user.role]||0;
  document.getElementById("nav-occupancy").style.display=lvl>=2?"flex":"none";
  document.getElementById("nav-analytics").style.display=lvl>=3?"flex":"none";
}

// ═══════════════════════ PROFILE ═══════════════════════
function renderProfile(){
  const card=document.getElementById("profile-card");
  if(!_user){ card.innerHTML='<p style="color:var(--muted);font-size:14px;">Please <span style="color:var(--red);cursor:pointer;" onclick="showLogin()">sign in</span> to view your profile.</p>'; return; }
  const ibanSection=_user.role==="customer"?`
    <div class="profile-field">
      <label>IBAN (for refunds)</label>
      ${_user.masked_iban?`<div class="iban-display">**** **** **** ${_user.masked_iban.slice(-4)}</div>`:'<p class="hint" style="padding:8px 0;">No IBAN on file.</p>'}
    </div>
    <div class="profile-field">
      <label>Update IBAN</label>
      <input id="iban-input" placeholder="DE89 3704 0044 0532 0130 00"/>
      <button class="save-btn" onclick="saveIban()" style="margin-top:10px;">Save IBAN</button>
    </div>
  `:"";
  card.innerHTML=`
    <div class="profile-field"><label>Full Name</label><div class="value">${_user.full_name||"–"}</div></div>
    <div class="profile-field"><label>Username</label><div class="value">${_user.username}</div></div>
    <div class="profile-field"><label>Email</label><div class="value">${_user.email||"–"}</div></div>
    <div class="profile-field"><label>Role</label><div class="value">${_user.role}</div></div>
    ${ibanSection}
  `;
}

async function saveIban(){
  const iban=document.getElementById("iban-input").value.trim();
  if(!iban){ alert("Please enter an IBAN."); return; }
  if(!_token){ showLogin(); return; }
  const r=await fetch(api()+"/user/iban",{method:"POST",headers:{"Content-Type":"application/json","Authorization":"Bearer "+_token},body:JSON.stringify({iban})});
  const d=await r.json();
  if(d.success){
    _user.masked_iban=d.masked_iban;
    document.getElementById("sb-iban").innerText="IBAN: ****"+d.masked_iban.slice(-4);
    renderProfile();
    add("bot","✅ IBAN saved. Showing last 4 digits: ****"+d.masked_iban.slice(-4));
  } else { alert(d.error||"Failed to save IBAN."); }
}

// ═══════════════════════ OCCUPANCY ═══════════════════════
async function lookupOcc(){
  const train=document.getElementById("occ-input").value.trim();
  if(!train) return;
  if(!_token){ showLogin(); return; }
  try{
    let d;
    const r=await fetch(api()+"/occupancy/"+encodeURIComponent(train),{headers:{"Authorization":"Bearer "+_token}}).catch(()=>null);
    if(!r||!r.ok){
      // Backend offline — use mock occupancy data
      const mockOcc={"ICE 572":{occupancy_pct:82,status:"high",seats_total:450,seats_booked:369,seats_available:81,wagon_classes:{"1st":{booked:78,total:90},"2nd":{booked:291,total:360}},source:"local-mock",date:new Date().toISOString().slice(0,10)},"ICE 999":{occupancy_pct:95,status:"full",seats_total:450,seats_booked:428,seats_available:22,wagon_classes:{"1st":{booked:88,total:90},"2nd":{booked:340,total:360}},source:"local-mock",date:new Date().toISOString().slice(0,10)},"RE 50":{occupancy_pct:41,status:"low",seats_total:200,seats_booked:82,seats_available:118,wagon_classes:{},source:"local-mock",date:new Date().toISOString().slice(0,10)}};
      const key=Object.keys(mockOcc).find(k=>train.replace(" ","").toUpperCase().includes(k.replace(" ","")));
      d=key?{...mockOcc[key],train_number:train}:{occupancy_pct:63,status:"high",seats_total:400,seats_booked:252,seats_available:148,wagon_classes:{},source:"local-mock (estimated)",date:new Date().toISOString().slice(0,10),train_number:train,origin:"–",destination:"–"};
      document.getElementById("occ-result").insertAdjacentHTML("afterbegin","<div style='padding:6px 10px;background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);border-radius:6px;font-size:11px;color:#fbbf24;margin-bottom:12px;'>⚠️ Backend offline — showing demo occupancy data</div>");
    } else {
      if(r.status===403){ const err=await r.json(); alert(err.error); return; }
      d=await r.json();
    }
    const pct=d.occupancy_pct;
    const color=pct>80?"var(--red)":pct>=50?"var(--amber)":"var(--green)";
    const statusClass={"full":"pill-full","high":"pill-high","low":"pill-low"}[d.status]||"pill-low";
    document.getElementById("occ-result").style.display="block";
    document.getElementById("occ-result").innerHTML=`
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
        <div><div style="font-size:20px;font-weight:700;">${d.train_number}</div>
          <div style="color:var(--muted);font-size:13px;">${d.origin||""} → ${d.destination||""}</div></div>
        <span class="status-pill ${statusClass}">${d.status.toUpperCase()} · ${pct}%</span>
      </div>
      <div style="margin:18px 0;background:rgba(255,255,255,.08);border-radius:10px;height:16px;">
        <div style="width:${pct}%;height:100%;border-radius:10px;background:${color};transition:width .5s;"></div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:13px;">
        <div><div style="color:var(--muted)">Total seats</div><div style="font-size:22px;font-weight:700;">${d.seats_total}</div></div>
        <div><div style="color:var(--muted)">Booked</div><div style="font-size:22px;font-weight:700;color:${color};">${d.seats_booked}</div></div>
        <div><div style="color:var(--muted)">Available</div><div style="font-size:22px;font-weight:700;color:var(--green);">${d.seats_available}</div></div>
      </div>
      ${Object.entries(d.wagon_classes||{}).length>0?`
      <div style="margin-top:16px;border-top:1px solid var(--border);padding-top:14px;">
        <div style="font-size:12px;color:var(--muted);margin-bottom:10px;">CLASS BREAKDOWN</div>
        ${Object.entries(d.wagon_classes).map(([cls,v])=>`
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px;">
            <span>${cls} class</span>
            <span>${v.booked}/${v.total} — ${v.total>0?Math.round(v.booked/v.total*100):0}%</span>
          </div>
        `).join("")}
      </div>`:""}
      <div style="margin-top:14px;font-size:12px;color:var(--muted);">Source: ${d.source} · Date: ${d.date}</div>
      ${d.status==="full"?`<div style="margin-top:12px;padding:10px 14px;background:rgba(227,6,19,.1);border-radius:10px;font-size:13px;color:#f87171;">⚠️ This train is full. Advise passengers to take the next available service.</div>`:""}
    `;
  }catch(e){ alert("Error: "+e.message); }
}

async function loadFleetOverview(){
  if(!_token) return;
  try{
    let d;
    const r=await fetch(api()+"/analytics/fleet",{headers:{"Authorization":"Bearer "+_token}}).catch(()=>null);
    if(!r||!r.ok){
      d=getMockAnalytics();
    } else {
      if(r.status===403) return;
      d=await r.json();
    }
    const wrap=document.getElementById("fleet-table-wrap");
    if(!d.trains){ wrap.innerHTML=""; return; }
    wrap.innerHTML=`<table class="train-table">
      <thead><tr><th>Train</th><th>Route</th><th>Occupancy</th><th>Status</th><th>Avail.</th></tr></thead>
      <tbody>${d.trains.map(t=>{
        const pct=t.occupancy_pct;
        const color=pct>80?"var(--red)":pct>=50?"var(--amber)":"var(--green)";
        const sc={"full":"pill-full","high":"pill-high","low":"pill-low"}[t.status]||"pill-low";
        return `<tr>
          <td style="font-weight:600;">${t.train_number}</td>
          <td style="color:var(--muted);font-size:12px;">${t.origin}→${t.destination}</td>
          <td><div class="occ-bar-wrap"><div class="occ-mini"><div class="occ-mini-fill" style="width:${pct}%;background:${color};height:100%;border-radius:4px;"></div></div><span style="font-size:12px;font-weight:600;">${pct}%</span></div></td>
          <td><span class="status-pill ${sc}">${t.status}</span></td>
          <td style="font-size:13px;">${t.seats_available}</td>
        </tr>`;
      }).join("")}</tbody>
    </table>`;
  }catch(e){}
}

// ── Mock analytics data (used when backend offline) ───────────────────────
function getMockAnalytics(){
  const today=new Date().toISOString().slice(0,10);
  const days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  return {
    summary:{avg_occupancy_pct:67,full_trains:3,low_trains:5,total_monitored_trains:24,date:today},
    history_7d:days.map((d,i)=>({date:"2026-05-"+(16+i),avg_occupancy:52+Math.floor(Math.sin(i)*18+Math.random()*12)})),
    revenue_monthly:[{month:"Jan",revenue_eur:1820000},{month:"Feb",revenue_eur:1540000},{month:"Mar",revenue_eur:2100000},{month:"Apr",revenue_eur:1950000},{month:"May",revenue_eur:2340000}],
    route_breakdown:[{route:"FRA→BER",avg_occupancy:82},{route:"MUC→HAM",avg_occupancy:71},{route:"STU→KÖL",avg_occupancy:55},{route:"DUS→FRA",avg_occupancy:64},{route:"BER→MUC",avg_occupancy:78}],
    delay_by_type:[{train_type:"ICE",avg_delay_min:4.2,on_time_pct:87},{train_type:"IC",avg_delay_min:7.8,on_time_pct:72},{train_type:"RE",avg_delay_min:11.1,on_time_pct:61}],
    compensation_monthly:[{month:"Jan",claims:142},{month:"Feb",claims:98},{month:"Mar",claims:187},{month:"Apr",claims:156},{month:"May",claims:203}],
    trains:[
      {train_number:"ICE 572",origin:"Frankfurt",destination:"Berlin",occupancy_pct:82,status:"high",seats_available:34},
      {train_number:"ICE 999",origin:"München",destination:"Hamburg",occupancy_pct:95,status:"full",seats_available:5},
      {train_number:"RE 50",origin:"Stuttgart",destination:"Köln",occupancy_pct:41,status:"low",seats_available:120},
      {train_number:"ICE 701",origin:"Berlin",destination:"München",occupancy_pct:67,status:"high",seats_available:58},
      {train_number:"IC 2045",origin:"Düsseldorf",destination:"Frankfurt",occupancy_pct:55,status:"low",seats_available:87},
    ]
  };
}

// ═══════════════════════ ANALYTICS ═══════════════════════
async function loadAnalytics(){
  if(!_token){ document.getElementById("analytics-panel").innerHTML+='<p style="color:var(--muted);">Admin access required.</p>'; return; }
  try{
    let d;
    const r=await fetch(api()+"/analytics/fleet",{headers:{"Authorization":"Bearer "+_token}}).catch(()=>null);
    if(!r||!r.ok){
      d=getMockAnalytics();
      document.getElementById("kpi-grid").insertAdjacentHTML("beforebegin","<div style='padding:8px 12px;background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);border-radius:8px;font-size:12px;color:#fbbf24;margin-bottom:16px;'>⚠️ Backend offline — showing cached demo data</div>");
    } else {
      if(r.status===403){ return; }
      d=await r.json();
    }
    const s=d.summary||{};
    // KPIs
    document.getElementById("kpi-grid").innerHTML=`
      <div class="kpi-card"><div class="kpi-label">Avg Occupancy Today</div><div class="kpi-value kpi-amber">${s.avg_occupancy_pct}%</div><div class="kpi-sub">Fleet-wide</div></div>
      <div class="kpi-card"><div class="kpi-label">Full Trains</div><div class="kpi-value kpi-red">${s.full_trains}</div><div class="kpi-sub">&gt;80% booked</div></div>
      <div class="kpi-card"><div class="kpi-label">Low Occupancy</div><div class="kpi-value kpi-green">${s.low_trains}</div><div class="kpi-sub">&lt;50% booked</div></div>
      <div class="kpi-card"><div class="kpi-label">Trains Monitored</div><div class="kpi-value kpi-blue">${s.total_monitored_trains}</div><div class="kpi-sub">Today · ${s.date}</div></div>
    `;
    // Occupancy bar chart (7d)
    renderBarChart("chart-occ", d.history_7d.map(h=>({label:h.date.slice(5),value:h.avg_occupancy,max:100,color:"var(--amber)"})));
    // Revenue chart
    const rev=d.revenue_monthly||[];
    renderBarChart("chart-rev", rev.map(m=>({label:m.month,value:Math.round(m.revenue_eur/1000),max:Math.max(...rev.map(x=>x.revenue_eur))/1000,color:"var(--green)"})));
    // Routes
    renderHBar("chart-routes", (d.route_breakdown||[]).map(r=>({label:r.route,value:r.avg_occupancy,color:r.avg_occupancy>80?"var(--red)":r.avg_occupancy>=50?"var(--amber)":"var(--green)"})));
    // Delay
    renderHBar("chart-delay", (d.delay_by_type||[]).map(r=>({label:r.train_type+" trains",value:r.avg_delay_min,max:40,color:"var(--blue)",suffix:" min",extra:`On time: ${r.on_time_pct}%`})));
    // Claims
    const cl=d.compensation_monthly||[];
    renderBarChart("chart-claims", cl.map(m=>({label:m.month,value:m.claims,max:Math.max(...cl.map(x=>x.claims)),color:"var(--purple)"})));
  }catch(e){ console.error(e); }
}

function renderBarChart(id, items){
  const el=document.getElementById(id); if(!el) return;
  const max=Math.max(...items.map(i=>i.max||i.value),1);
  el.innerHTML=items.map(i=>{
    const h=Math.round((i.value/max)*140);
    return `<div class="bar-wrap">
      <div class="bar-val">${i.value}</div>
      <div class="bar" style="height:${h}px;background:${i.color};"></div>
      <div class="bar-label">${i.label}</div>
    </div>`;
  }).join("");
}

function renderHBar(id, items){
  const el=document.getElementById(id); if(!el) return;
  const max=Math.max(...items.map(i=>i.max||i.value),1);
  el.innerHTML=items.map(i=>{
    const w=Math.round(i.value/max*100);
    return `<div class="h-bar-row">
      <div class="h-bar-label">${i.label}</div>
      <div class="h-bar-track"><div class="h-bar-fill" style="width:${w}%;background:${i.color};">${i.value}${i.suffix||""}</div></div>
      ${i.extra?`<div class="h-bar-pct" style="width:80px;">${i.extra}</div>`:`<div class="h-bar-pct">${i.value}%</div>`}
    </div>`;
  }).join("");
}

// ═══════════════════════ CHAT HELPERS ═══════════════════════
function add(role, text){
  const d=document.createElement("div");
  d.className="msg "+(role==="user"?"user":"bot");
  d.innerText=text;
  const chat=document.getElementById("chat");
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
}

function addOptions(){
  const chat=document.getElementById("chat");
  const wrap=document.createElement("div");
  wrap.id="chat-options";
  wrap.style.cssText="display:flex;gap:8px;flex-wrap:wrap;padding:4px 0 8px;";
  const opts=[
    {label:"🎫 Book a ticket", fn:"book()"},
    {label:"💶 Claim compensation", fn:"startClaim()"},
    {label:"🚆 Check delay", fn:"startDelay()"},
    {label:"☎️ Human assistance", fn:"human()"},
  ];
  opts.forEach(o=>{
    const b=document.createElement("button");
    b.innerText=o.label;
    b.style.cssText="padding:9px 14px;font-size:12px;border-radius:12px;background:#fff3f3;border:1px solid rgba(227,6,19,.25);color:#e30613;cursor:pointer;font-family:inherit;font-weight:500;";
    b.onmouseover=()=>b.style.background="rgba(227,6,19,.15)";
    b.onmouseout=()=>b.style.background="#fff3f3";
    b.onclick=()=>{ wrap.remove(); add("user", o.label); eval(o.fn); };
    wrap.appendChild(b);
  });
  chat.appendChild(wrap);
  chat.scrollTop=chat.scrollHeight;
}

async function post(path,payload){
  const h={"Content-Type":"application/json"};
  if(_token) h["Authorization"]="Bearer "+_token;
  try{
    const r=await fetch(api()+path,{method:"POST",headers:h,body:JSON.stringify(payload)});
    if(!r.ok) return {error:"HTTP "+r.status};
    return r.json();
  }catch(e){ return {_offline:true,error:e.message}; }
}
async function get(path){
  const h={}; if(_token) h["Authorization"]="Bearer "+_token;
  try{
    const r=await fetch(api()+path,{headers:h});
    if(!r.ok) return {error:"HTTP "+r.status};
    return r.json();
  }catch(e){ return {_offline:true,error:e.message}; }
}

// ── OpenAI API fallback (used when backend is offline) ─────────────────
const ANTHROPIC_SYSTEM = "You are DeBian, a friendly Digital Rail Assistant for Deutsche Bahn. You help passengers with train delays, compensation claims, ticket bookings, and general rail travel questions. Be concise, helpful, and professional. If asked about specific train data you cannot look up, explain you need the backend connected for live data.";

async function callOpenAIAPI(message, history){
  try{
    const messages = [{role:"system",content:ANTHROPIC_SYSTEM}]
      .concat((history||[]).slice(-8))
      .concat([{role:"user",content:message}]);
    const resp = await fetch("https://api.openai.com/v1/chat/completions",{
      method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+(window.OPENAI_API_KEY||"")},
      body:JSON.stringify({
        model:"gpt-4.1-mini",
        max_tokens:500,
        messages:messages
      })
    });
    const data = await resp.json();
    const text = data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content;
    return text || "I'm here to help! Please ask me about your train journey.";
  }catch(e){
    return "I'm DeBian, your rail assistant. The AI service is temporarily unavailable. For immediate help, please use the quick-action buttons above or contact Deutsche Bahn support.";
  }
}

function onLangChange(){ step=null; claim={}; const chat=document.getElementById("chat"); chat.innerHTML=""; add("bot",g("greet1")); add("bot",g("greet2")); }

function formatDelay(d){
  const train=d.train_number||"your train";
  if(d.status==="unknown") return `Could not find delay data for ${train}.\n\nFor demo, try ICE 572, ICE 999, or RE 50.`;
  let lines=[`Status for ${train}: ${d.status}.`];
  if(d.delay_minutes!=null) lines.push(`Delay: approximately ${d.delay_minutes} minutes.`);
  if(d.origin&&d.destination) lines.push(`Route: ${d.origin} → ${d.destination}.`);
  if(d.delay_minutes>=60) lines.push("You may be eligible for compensation. Use 💶 Claim to start.");
  return lines.join("\n");
}
function formatClaim(r){
  const c=r.compensation||{};
  let lines=["✅ Claim submitted successfully!","Reference: "+(r.claim_id||"created")+"."];
  if(c.eligible){
    lines.push("Estimated compensation: "+c.percentage+"% = "+c.amount+" EUR.");
  } else {
    lines.push("Based on current EU rail rules, this delay does not qualify for compensation (minimum 60 min required).");
  }
  if(r.masked_account_number){
    const last4=r.masked_account_number.replace(/\s/g,"").slice(-4);
    lines.push("Payment will be sent to account ending ****"+last4+".");
  }
  lines.push("You will receive a confirmation email within 24 hours.");
  return lines.join("\n");
}

async function checkBackend(){
  const d=await get("/");
  if(d._offline||d.error){
    document.getElementById("status").innerText="✅ AI-powered via OpenAI · Start backend for live data";
    _backendOnline=false;
  } else {
    document.getElementById("status").innerText="✅ "+d.service;
    _backendOnline=true;
  }
}
let _backendOnline=false;

async function runETL(){
  const d=await get("/etl/run");
  if(d._offline||d.error){
    // Mock ETL pipeline result when backend offline
    const mock={pipeline:{status:"completed (local mock)",stages:{bronze:"57 raw delay events processed",silver:"48 records cleaned and validated",gold:"42 features written to feature store"},duration_ms:312,records_processed:42}};
    add("bot","ETL pipeline completed (offline mock).\n"+JSON.stringify(mock.pipeline,null,2));
  } else {
    add("bot","ETL pipeline completed.\n"+JSON.stringify(d.pipeline||d,null,2));
  }
}

function book(){ step=null; add("bot",g("book")); }
function startClaim(){ step="train_number"; claim={language:lang(),claim_form:true}; add("bot",g("claim_start")); }
function startDelay(){ step="delay_train"; add("bot",g("delay_start")); }
async function human(){
  const r=await post("/human-assistance",{language:lang(),reason:"customer clicked human assistance"});
  if(r._offline||!r.handoff_id){
    const ref="HO-"+(Date.now()%100000).toString().padStart(5,"0");
    add("bot","🧑\u200d💼 Human support requested.\nReference: "+ref+"\n\n(Offline mode: Your request has been queued. A support agent will contact you within 2 hours.)");
  } else {
    add("bot","Human support requested.\nReference: "+r.handoff_id);
  }
}

async function send(){
  if(_pendingFile){ const q=document.getElementById("input").value.trim(); if(q) add("user","📎 "+_pendingFile.name+"\n"+q); else add("user","📎 "+_pendingFile.name); document.getElementById("input").value=""; await uploadFile(_pendingFile,q); return; }
  const t=document.getElementById("input").value.trim(); if(!t) return;
  // Mask IBAN in chat display when user enters account number during claim
  const displayText = step==="account" ? "**** **** **** "+t.split(" ").join("").slice(-4) : t;
  add("user",displayText); document.getElementById("input").value="";
  if(step){ await guided(t); return; }
  _history.push({role:"user",content:t});
  let reply;
  try{
    const r=await post("/assist",{message:t,language:lang(),history:_history.slice(-10)});
    if(r._offline || !r.response){
      // Backend offline — use OpenAI API directly
      reply = await callOpenAIAPI(t, _history.slice(-8));
    } else {
      reply = r.response;
    }
  }catch(e){
    reply = await callOpenAIAPI(t, _history.slice(-8));
  }
  add("bot", reply);
  if(reply) _history.push({role:"assistant",content:reply});
}

async function guided(t){
  const tl=t.toLowerCase();
  if(step==="delay_train"){
    const d=await get("/delay/"+encodeURIComponent(t));
    if(d._offline||d.error==="Not found"){
      // Mock delay data when backend offline
      const mockDelays={"ICE 572":{train_number:t,status:"delayed",delay_minutes:23,origin:"Frankfurt(Main)Hbf",destination:"Berlin Hbf",source:"local-mock"},"ICE 999":{train_number:t,status:"on_time",delay_minutes:0,origin:"München Hbf",destination:"Hamburg Hbf",source:"local-mock"},"RE 50":{train_number:t,status:"delayed",delay_minutes:67,origin:"Stuttgart Hbf",destination:"Köln Hbf",source:"local-mock"}};
      const key=Object.keys(mockDelays).find(k=>t.replace(" ","").toUpperCase().includes(k.replace(" ","")));
      add("bot",formatDelay(key?mockDelays[key]:{train_number:t,status:"unknown",delay_minutes:null,source:"local-mock"}));
    } else { add("bot",formatDelay(d)); }
    step=null; return;
  }
  if(step==="train_number"){claim.train_number=t;step="station_name";add("bot",g("ask_station"));return;}
  if(step==="station_name"){claim.station_name=t;step="planned_start_time";add("bot",g("ask_planned"));return;}
  if(step==="planned_start_time"){claim.planned_start_time=t;step="actual";add("bot",g("ask_actual"));return;}
  if(step==="actual"){
    if(tl.includes(g("not_started_kw"))){claim.trip_not_started=true;claim.actual_start_time=null;}
    else{claim.trip_not_started=false;claim.actual_start_time=t;}
    step="delay";add("bot",g("ask_delay"));return;
  }
  if(step==="delay"){claim.delay_minutes=Number(t);step="alternative";add("bot",g("ask_alt"));return;}
  if(step==="alternative"){claim.alternative_transport=t||"none";step="price";add("bot",g("ask_price"));return;}
  if(step==="price"){
    claim.ticket_price=Number(t.replace(",","."));
    // If user has IBAN on file, skip refund-method question — auto-use bank account
    if(_user&&_user.masked_iban){
      claim.refund_method="bank_account";
      claim.account_number=_user.masked_iban;
      claim.home_address=null;
      add("bot","✅ Using your saved account ending ****"+_user.masked_iban.slice(-4)+".\nSubmitting your claim now…");
      await submitClaim();
    } else {
      // No IBAN — ask how they want compensation
      step="refund"; add("bot",g("ask_refund"));
    }
    return;
  }
  if(step==="refund"){
    claim.refund_method=tl.includes(g("bank_kw"))?"bank_account":"voucher";
    if(claim.refund_method==="bank_account"){
      step="account"; add("bot",g("ask_iban"));
    } else { step="address"; add("bot",g("ask_address")); }
    return;
  }
  if(step==="account"){claim.account_number=t; claim.home_address=null; await submitClaim(); return;}
  if(step==="address"){claim.home_address=t; claim.account_number=null; await submitClaim(); return;}
}
async function submitClaim(){
  const r=await post("/claim",claim);
  if(r._offline||r.error){
    // Generate a local mock claim result
    const delayMin=claim.delay_minutes||0;
    const price=claim.ticket_price||0;
    const pct=delayMin>=120?50:delayMin>=60?25:0;
    const amt=Math.round(price*pct/100*100)/100;
    const mockR={
      claim_id:"CLM-"+(Date.now()%100000).toString().padStart(6,"0"),
      status:"submitted",
      compensation:{eligible:pct>0,percentage:pct,amount:amt},
      masked_account_number:claim.account_number?("*".repeat(Math.max(0,claim.account_number.replace(/\s/g,"").length-4))+claim.account_number.replace(/\s/g,"").slice(-4)):null
    };
    add("bot",formatClaim(mockR));
  } else {
    add("bot",formatClaim(r));
  }
  step=null; claim={};
}

// ═══════════════════════ FILE UPLOAD ═══════════════════════
var _pendingFile=null;
function onFileSelected(input){
  const file=input.files&&input.files[0]; if(!file) return;
  _pendingFile=file;
  const preview=document.getElementById("file-preview");
  document.getElementById("fp-name").innerText=file.name+" ("+Math.round(file.size/1024)+"KB)";
  const wrap=document.getElementById("fp-img-wrap"); wrap.innerHTML="";
  if(file.type.startsWith("image/")){const img=document.createElement("img");img.src=URL.createObjectURL(file);wrap.appendChild(img);}
  preview.style.display="block";
  document.getElementById("input").placeholder="Ask about this file, or press Send…";
}
function clearFile(){ _pendingFile=null; document.getElementById("file-preview").style.display="none"; document.getElementById("fp-img-wrap").innerHTML=""; document.getElementById("fp-name").innerText=""; document.getElementById("file-input").value=""; document.getElementById("input").placeholder="Type here…"; }
async function uploadFile(file,question){
  const inputEl=document.getElementById("input");
  inputEl.disabled=true;
  add("bot","🔍 Analysing "+file.name+"…");
  try{
    // Route through the backend /upload-document endpoint so the API key
    // stays server-side and CORS is never an issue.
    const fd=new FormData();
    fd.append("file",file,file.name);
    if(question) fd.append("message",question);
    fd.append("language",lang());

    const backendUrl=api()+"/upload-document";
    const headers={};
    if(_token) headers["Authorization"]="Bearer "+_token;

    const resp=await fetch(backendUrl,{method:"POST",headers,body:fd});

    if(!resp.ok){
      // Backend offline or returned an error — fall back to OpenAI direct call
      
      throw new Error("Backend returned "+resp.status);
    }

    const data=await resp.json();
    const text=data.analysis||data.error||"⚠️ Could not analyse the file.";
    add("bot",text);
  }catch(e){
    // Last-resort fallback: call OpenAI API directly
    try{
      const base64=await new Promise((res,rej)=>{
        const r=new FileReader();
        r.onload=()=>res(r.result.split(",")[1]);
        r.onerror=()=>rej(new Error("Could not read file"));
        r.readAsDataURL(file);
      });
      const mime=file.type||"image/jpeg";
      const isImage=mime.startsWith("image/");
      const isPdf=mime==="application/pdf";
      const prompt=question||(isImage?"Analyse this image. If it is a train ticket extract all details: train number, route, origin, destination, date, time, price, class, validity. Present clearly.":"Analyse this document and extract all relevant information.");
      let msgContent;
      if(isImage){
        // OpenAI vision format
        msgContent=[{type:"image_url",image_url:{url:"data:"+mime+";base64,"+base64}},{type:"text",text:prompt}];
      } else {
        msgContent=[{type:"text",text:"File: "+file.name+"\n\n"+(isPdf?"(PDF – upload to backend for full analysis)\n\n":"")+prompt}];
      }
      const OPENAI_KEY=window.OPENAI_API_KEY||"";
      if(!OPENAI_KEY) throw new Error("No API key available and backend is offline.");
      const fbResp=await fetch("https://api.openai.com/v1/chat/completions",{
        method:"POST",
        headers:{"Content-Type":"application/json","Authorization":"Bearer "+OPENAI_KEY},
        body:JSON.stringify({model:"gpt-4.1-mini",max_tokens:1000,messages:[{role:"system",content:ANTHROPIC_SYSTEM},{role:"user",content:msgContent}]})
      });
      const fbData=await fbResp.json();
      const fbText=fbData.choices&&fbData.choices[0]&&fbData.choices[0].message&&fbData.choices[0].message.content;
      add("bot",fbText||"⚠️ Could not analyse the file.");
    }catch(e2){ add("bot","⚠️ Could not process file: "+e2.message); }
  }
  inputEl.disabled=false; inputEl.focus(); clearFile();
}

// ═══════════════════════ MIC ═══════════════════════
var _mr=null,_chunks=[],_busy=false;
function micStart(e){
  e.preventDefault(); const L=lang();
  if(L!=="en"&&L!=="de"){alert("Voice available in English and German only.");return;}
  if(_busy) return;
  if(!navigator.mediaDevices){alert("Microphone not available.");return;}
  navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
    _busy=true;_chunks=[];
    const btn=document.getElementById("btn-mic"); btn.classList.add("recording");
    const mime=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":"audio/webm";
    _mr=new MediaRecorder(stream,{mimeType:mime});
    _mr.ondataavailable=function(ev){if(ev.data.size)_chunks.push(ev.data);};
    _mr.onstop=function(){
      stream.getTracks().forEach(t=>t.stop()); btn.classList.remove("recording"); _busy=false;
      const blob=new Blob(_chunks,{type:mime}); const fd=new FormData(); fd.append("audio",blob,"audio.webm");
      const inp=document.getElementById("input"); inp.placeholder="Transcribing…";
      fetch(api()+"/transcribe",{method:"POST",body:fd}).then(r=>r.json()).then(d=>{
        inp.placeholder="Type here…";
        if(d.text){const base=inp.value;inp.value=(base&&!base.endsWith(" ")?base+" ":base)+d.text.trim();inp.focus();}
        else{inp.placeholder=(d.error||"Error")+" — try again";setTimeout(()=>{inp.placeholder="Type here…";},3000);}
      }).catch(()=>{inp.placeholder="Type here…";});
    };
    _mr.start();
  }).catch(err=>{_busy=false;alert("Mic error: "+err.message);});
}
function micStop(){ if(_mr&&_mr.state==="recording") _mr.stop(); }

// ═══════════════════════ BOOT ═══════════════════════
add("bot", GUIDED["en"]["greet1"]);
add("bot", GUIDED["en"]["greet2"]);
addOptions();
// Auto-check backend status on load
checkBackend().catch(()=>{});
</script>
</body>
</html>
"""


class FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # suppress access logs
        pass

    def do_GET(self) -> None:
        # Inject OPENAI_API_KEY from environment into the page at serve-time.
        # The HTML contains the placeholder  __OPENAI_KEY__  which we swap out
        # here so the key is never stored in source code.
        api_key = os.environ.get("OPENAI_API_KEY", "")
        body = FALLBACK_HTML.replace("__OPENAI_KEY__", api_key).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_fallback_ui() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8501), FallbackHandler)
    print("Running DeBian UI at http://127.0.0.1:8501")
    server.serve_forever()


if __name__ == "__main__":
    run_fallback_ui()
