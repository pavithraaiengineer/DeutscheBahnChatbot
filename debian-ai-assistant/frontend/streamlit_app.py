"""
DeBian guided frontend.

Run:
    python frontend\\streamlit_app.py

Open:
    http://127.0.0.1:8501
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
<html>
<head>
  <meta charset="UTF-8" />
  <title>DeBian Guided Chatbot</title>
  <style>
    :root { --red:#e30613; --bg:#111113; --panel:rgba(255,255,255,.08); --border:rgba(255,255,255,.14); --muted:#aaa; }
    body { margin:0; font-family:Arial,sans-serif; background:radial-gradient(circle at 70% 80%, rgba(227,6,19,.32), transparent 32%), radial-gradient(circle at 20% 20%, rgba(57,86,255,.20), transparent 24%), var(--bg); color:white; min-height:100vh; }
    main { max-width:1120px; margin:0 auto; padding:28px; display:grid; grid-template-columns:340px 1fr; gap:22px; }
    section { background:var(--panel); border:1px solid var(--border); border-radius:28px; padding:26px; box-shadow:0 20px 70px rgba(0,0,0,.35); }
    h1 { font-size:60px; margin:28px 0 4px; letter-spacing:-2px; } h1 span { color:var(--red); }
    input, select, button { width:100%; box-sizing:border-box; padding:13px; border-radius:14px; margin:8px 0; background:rgba(0,0,0,.28); color:white; border:1px solid var(--border); }
    button { background:var(--red); border:none; cursor:pointer; font-weight:bold; }
    .secondary { background:rgba(255,255,255,.12); border:1px solid var(--border); }
    .quick { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin:16px 0; }
    .chat { height:540px; overflow-y:auto; background:rgba(0,0,0,.25); border:1px solid var(--border); border-radius:20px; padding:16px; }
    .msg { max-width:84%; padding:12px 14px; border-radius:16px; margin:10px 0; white-space:pre-wrap; line-height:1.45; }
    .bot { background:rgba(255,255,255,.12); border:1px solid var(--border); }
    .user { background:var(--red); margin-left:auto; }
    .row { display:flex; gap:10px; margin-top:14px; align-items:stretch; }
    .row #input { flex:1 !important; width:auto !important; min-width:0; margin:0; }
    .row #btn-mic { flex:0 0 52px !important; width:52px !important; margin:0; padding:0; }
    .row #btn-upload { flex:0 0 52px !important; width:52px !important; margin:0; padding:0; }
    .row #btn-send { flex:0 0 130px !important; width:130px !important; margin:0; }
    #btn-upload { flex-shrink:0; width:52px; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.14); border-radius:14px; cursor:pointer; color:white; display:inline-flex; align-items:center; justify-content:center; user-select:none; -webkit-user-select:none; transition:background .15s; }
    #btn-upload:hover { background:rgba(255,255,255,.22); }
    #file-preview { margin-top:10px; display:none; background:rgba(255,255,255,.07); border:1px solid var(--border); border-radius:14px; padding:10px 14px; font-size:13px; color:var(--muted); position:relative; }
    #file-preview .fp-name { color:white; font-weight:bold; margin-bottom:4px; }
    #file-preview img { max-height:120px; border-radius:8px; margin-top:6px; display:block; }
    #file-preview .fp-clear { position:absolute; top:8px; right:10px; cursor:pointer; color:var(--muted); font-size:18px; line-height:1; }
    #btn-mic { flex-shrink:0; width:52px; background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.14); border-radius:14px; cursor:pointer; color:white; display:inline-flex; align-items:center; justify-content:center; user-select:none; -webkit-user-select:none; transition:background .15s; }
    #btn-mic.recording { background:#e30613; border-color:#e30613; animation:pulse .8s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.55} }
    .hint { color:var(--muted); font-size:13px; line-height:1.4; }
    @media(max-width:900px){ main{grid-template-columns:1fr; padding:18px;} }
  </style>
</head>
<body>
<main>
<section>
  <h1>De<span>Bi</span>an</h1>
  <p>Your Digital Rail Assistant</p>
  <input id="apiBase" value="http://127.0.0.1:8000" />
  <select id="language" onchange="onLangChange()">
""" + _LANG_OPTIONS_HTML + r"""
  </select>
  <button class="secondary" onclick="checkBackend()">Check Backend</button>
  <button class="secondary" onclick="runETL()">Run ETL</button>
  <button class="secondary" onclick="infra()">Infra Status</button>
  <p id="status" class="hint">Start backend first: python -m app.main</p>
</section>
<section>
  <h2 id="hdr-title">Hello! 👋</h2>
  <p class="hint" id="hdr-sub">I am DeBian. I can help with delay checks, compensation claims, alternative routes, and human support.</p>
  <div class="quick">
    <button id="btn-book" onclick="book()">🎫 Book a ticket</button>
    <button id="btn-claim" onclick="startClaim()">💶 Claim compensation</button>
    <button id="btn-delay" onclick="startDelay()">🚆 Check delay</button>
    <button id="btn-human" onclick="human()">☎️ Human assistance</button>
  </div>
  <div id="chat" class="chat"></div>
  <div id="file-preview">
    <span class="fp-clear" onclick="clearFile()">✕</span>
    <div class="fp-name" id="fp-name"></div>
    <div id="fp-img-wrap"></div>
  </div>
  <div class="row"><input id="input" placeholder="Type here..." onkeydown="if(event.key==='Enter')send()" /><button id="btn-upload" onclick="document.getElementById('file-input').click()" title="Upload document or image"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></button><input type="file" id="file-input" accept="image/*,.pdf,.txt,.doc,.docx" style="display:none" onchange="onFileSelected(this)"/><button id="btn-mic" onmousedown="micStart(event)" onmouseup="micStop()" onmouseleave="micStop()" ontouchstart="micStart(event)" ontouchend="micStop()"><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg></button><button onclick="send()" id="btn-send">Send</button></div>
</section>
</main>
<script>
// -----------------------------------------------------------------------
// Guided-flow string tables (mirrors backend GUIDED dict)
// -----------------------------------------------------------------------
const GUIDED = """ + str(GUIDED).replace("True", "true").replace("False", "false").replace("None", "null") + r""";

function g(key){ return (GUIDED[lang()] || GUIDED["en"])[key] || GUIDED["en"][key]; }

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
let step = null, claim = {};

function api(){ return document.getElementById("apiBase").value.replace(/\/$/, ""); }
function lang(){ return document.getElementById("language").value; }

function add(role, text){
  let d = document.createElement("div");
  d.className = "msg " + (role === "user" ? "user" : "bot");
  d.innerText = text;
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

async function post(path, payload){
  let r = await fetch(api() + path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  return await r.json();
}
async function get(path){ let r = await fetch(api() + path); return await r.json(); }

// -----------------------------------------------------------------------
// Language change — reset chat to greeting in new language
// -----------------------------------------------------------------------
function onLangChange(){
  step = null; claim = {};
  chat.innerHTML = "";
  add("bot", g("greet1"));
  add("bot", g("greet2"));
  document.getElementById("input").placeholder = lang() === "ar" ? "اكتب هنا..." : "Type here...";
}

// -----------------------------------------------------------------------
// Response formatters (unchanged from original)
// -----------------------------------------------------------------------
function formatDelay(d){
  const train = d.train_number || "your train";
  if(d.status === "unknown"){
    return `I could not find delay data for ${train} yet.\n\nFor this demo, try ICE 572, ICE 999, or RE 50.\nFor live mode, configure DB API credentials and provide station name plus planned start time.`;
  }
  let lines = [`Status for ${train}: ${d.status}.`];
  if(d.delay_minutes !== null && d.delay_minutes !== undefined) lines.push(`Delay: approximately ${d.delay_minutes} minutes.`);
  if(d.origin && d.destination) lines.push(`Route: ${d.origin} → ${d.destination}.`);
  if(d.station_name) lines.push(`Station: ${d.station_name}.`);
  if(d.planned_start_time) lines.push(`Planned start time: ${d.planned_start_time}.`);
  if(d.actual_start_time) lines.push(`Actual start time: ${d.actual_start_time}.`);
  if(d.platform) lines.push(`Platform: ${d.platform}.`);
  if(String(d.source || "").startsWith("mock")) lines.push("Note: this is demo data. For live data, configure DB API credentials.");
  if(d.delay_minutes >= 60) lines.push("You may be able to continue with a compensation claim.");
  return lines.join("\n");
}

function formatClaim(r){
  let c = r.compensation || {};
  let lines = [`Your compensation claim has been submitted.\nReference: ${r.claim_id || "created"}.`];
  if(c.eligible){
    lines.push(`Estimated compensation: ${c.percentage}% = ${c.amount} ${c.currency || "EUR"}.`);
  } else {
    lines.push("Based on the demo rules, this journey is probably not eligible for compensation.");
  }
  if(r.masked_account_number) lines.push(`Confirmed account: ${r.masked_account_number}.`);
  if(r.home_address_confirmed) lines.push("Voucher delivery address has been confirmed.");
  lines.push("Sensitive data has been masked.");
  return lines.join("\n");
}

// -----------------------------------------------------------------------
// Sidebar actions
// -----------------------------------------------------------------------
async function checkBackend(){
  try{
    let d = await get("/");
    status.innerText = "✅ " + d.service + " | LLM configured: " + d.config.llm_configured;
  } catch(e){ status.innerText = "❌ Backend not reachable"; }
}
async function runETL(){
  let d = await get("/etl/run");
  add("bot", `Data layer pipeline completed.\n\nBronze, Silver, and Gold layers were generated.\nPipeline: ${d.pipeline}`);
}
async function infra(){
  let d = await get("/infra/status");
  add("bot", `Infrastructure status checked.\n\nLLM configured: ${d.config.llm_configured}\nPinecone configured: ${d.config.pinecone_configured}\nDatabricks configured: ${d.config.databricks_configured}\nSession store: ${d.session_store.mode}`);
}

// -----------------------------------------------------------------------
// Guided flows — use language-aware prompts
// -----------------------------------------------------------------------
function book(){ step = null; add("bot", g("book")); }

function startClaim(){
  step = "train_number";
  claim = {language: lang(), claim_form: true};
  add("bot", g("claim_start"));
}

function startDelay(){ step = "delay_train"; add("bot", g("delay_start")); }

async function human(){
  const r = await post("/human-assistance", {language: lang(), reason: "customer clicked human assistance"});
  add("bot", `${g("greet1").split("!")[0]}!\nReference: ${r.handoff_id}\nStatus: ${r.handoff_status}`);
}

var _history = [];
async function send(){
  let t = input.value.trim();
  if(!t) return;
  add("user", t);
  input.value = "";
  if(step){ await guided(t); return; }
  _history.push({role:"user", content: t});
  let r = await post("/assist", {message: t, language: lang(), history: _history.slice(-10)});
  add("bot", r.response);
  if(r.response) _history.push({role:"assistant", content: r.response});
}

async function guided(t){
  const tl = t.toLowerCase();
  const notStartedKw = g("not_started_kw");
  const bankKw       = g("bank_kw");
  const voucherKw    = g("voucher_kw");

  if(step === "delay_train"){
    const d = await get("/delay/" + encodeURIComponent(t));
    add("bot", formatDelay(d));
    step = null;
    return;
  }
  if(step === "train_number")    { claim.train_number = t; step = "station_name";    add("bot", g("ask_station"));  return; }
  if(step === "station_name")    { claim.station_name = t; step = "planned_start_time"; add("bot", g("ask_planned")); return; }
  if(step === "planned_start_time"){ claim.planned_start_time = t; step = "actual"; add("bot", g("ask_actual")); return; }
  if(step === "actual"){
    if(tl.includes(notStartedKw)){ claim.trip_not_started = true; claim.actual_start_time = null; }
    else { claim.trip_not_started = false; claim.actual_start_time = t; }
    step = "delay"; add("bot", g("ask_delay")); return;
  }
  if(step === "delay")    { claim.delay_minutes = Number(t); step = "alternative"; add("bot", g("ask_alt"));    return; }
  if(step === "alternative"){ claim.alternative_transport = t || "none"; step = "price"; add("bot", g("ask_price")); return; }
  if(step === "price")    { claim.ticket_price = Number(t.replace(",", ".")); step = "refund"; add("bot", g("ask_refund")); return; }
  if(step === "refund"){
    claim.refund_method = tl.includes(bankKw) ? "bank_account" : "voucher";
    if(claim.refund_method === "bank_account"){ step = "account"; add("bot", g("ask_iban")); }
    else                                      { step = "address"; add("bot", g("ask_address")); }
    return;
  }
  if(step === "account"){ claim.account_number = t; claim.home_address = null; await submit(); return; }
  if(step === "address"){ claim.home_address = t; claim.account_number = null; await submit(); return; }
}

async function submit(){
  let r = await post("/claim", claim);
  add("bot", formatClaim(r));
  step = null; claim = {};
}

// -----------------------------------------------------------------------

// -----------------------------------------------------------------------
// Press-and-hold mic — records audio, sends to /transcribe (Whisper API)
// Transcript fills the input box. User reviews then presses Send.
// Only available when English or German is selected.
// -----------------------------------------------------------------------
var _mr = null, _chunks = [], _busy = false;

function micStart(e) {
  e.preventDefault();
  var L = lang();
  if (L !== 'en' && L !== 'de') { alert('Voice input is available in English and German only.'); return; }
  if (_busy) return;
  if (!navigator.mediaDevices) { alert('Microphone not available in this browser.'); return; }
  navigator.mediaDevices.getUserMedia({audio: true}).then(function(stream) {
    _busy = true; _chunks = [];
    var btn = document.getElementById('btn-mic');
    btn.classList.add('recording');
    var mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
    _mr = new MediaRecorder(stream, {mimeType: mime});
    _mr.ondataavailable = function(ev) { if (ev.data.size) _chunks.push(ev.data); };
    _mr.onstop = function() {
      stream.getTracks().forEach(function(t) { t.stop(); });
      btn.classList.remove('recording');
      _busy = false;
      var blob = new Blob(_chunks, {type: mime});
      var fd = new FormData();
      fd.append('audio', blob, 'audio.webm');
      var inp = document.getElementById('input');
      inp.placeholder = 'Transcribing\u2026';
      fetch(api() + '/transcribe', {method: 'POST', body: fd})
        .then(function(r) { return r.json(); })
        .then(function(d) {
          inp.placeholder = 'Type here...';
          if (d.text) {
            var base = inp.value;
            if (base && !base.endsWith(' ')) base += ' ';
            inp.value = base + d.text.trim();
            inp.focus();
          } else {
            inp.placeholder = (d.error || 'Error') + ' \u2014 try again';
            setTimeout(function() { inp.placeholder = 'Type here...'; }, 3000);
          }
        })
        .catch(function() { inp.placeholder = 'Type here...'; });
    };
    _mr.start();
  }).catch(function(err) { _busy = false; alert('Mic error: ' + err.message); });
}

function micStop() {
  if (_mr && _mr.state === 'recording') _mr.stop();
}

// -----------------------------------------------------------------------
// Document / image upload
// -----------------------------------------------------------------------
var _pendingFile = null;

function onFileSelected(input) {
  var file = input.files && input.files[0];
  if (!file) return;
  _pendingFile = file;
  var preview = document.getElementById('file-preview');
  document.getElementById('fp-name').innerText = file.name + ' (' + (file.size > 1024*1024 ? (file.size/1024/1024).toFixed(1)+'MB' : Math.round(file.size/1024)+'KB') + ')';
  var wrap = document.getElementById('fp-img-wrap');
  wrap.innerHTML = '';
  if (file.type.startsWith('image/')) {
    var img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    wrap.appendChild(img);
  }
  preview.style.display = 'block';
  // hint the user they can optionally type a question
  document.getElementById('input').placeholder = 'Ask something about this file, or press Send…';
}

function clearFile() {
  _pendingFile = null;
  document.getElementById('file-preview').style.display = 'none';
  document.getElementById('fp-img-wrap').innerHTML = '';
  document.getElementById('fp-name').innerText = '';
  document.getElementById('file-input').value = '';
  document.getElementById('input').placeholder = 'Type here...';
}

async function uploadFile(file, question) {
  var fd = new FormData();
  fd.append('file', file, file.name);
  if (question) fd.append('message', question);
  fd.append('language', lang());
  var inp = document.getElementById('input');
  inp.disabled = true;
  try {
    var r = await fetch(api() + '/upload-document', {method: 'POST', body: fd});
    var d = await r.json();
    if (d.error) {
      add('bot', '⚠️ Upload error: ' + d.error);
    } else {
      add('bot', '📎 ' + (d.file_name || file.name) + '\n\n' + (d.analysis || 'No analysis returned.'));
    }
  } catch(e) {
    add('bot', '⚠️ Could not reach backend for document analysis: ' + e.message);
  }
  inp.disabled = false;
  inp.focus();
  clearFile();
}

// Override send() to handle pending file
var _origSend = send;
send = async function() {
  if (_pendingFile) {
    var q = document.getElementById('input').value.trim();
    if (q) add('user', '📎 ' + _pendingFile.name + '\n' + q);
    else   add('user', '📎 ' + _pendingFile.name);
    document.getElementById('input').value = '';
    await uploadFile(_pendingFile, q);
    return;
  }
  await _origSend();
};

// Boot
// -----------------------------------------------------------------------
add("bot", GUIDED["en"]["greet1"]);
add("bot", GUIDED["en"]["greet2"]);
</script>
</body>
</html>
"""


class FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # suppress access logs
        pass

    def do_GET(self) -> None:
        body = FALLBACK_HTML.encode("utf-8")
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
