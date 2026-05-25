"""
DeBian – Synthetic RAG Compensation & Offer Documents
======================================================
Drop-in extension for scripts/seed_pinecone.py.

Usage
-----
    from rag_compensation_docs import COMPENSATION_DOCS
    POLICY_DOCS.extend(COMPENSATION_DOCS)          # in seed_pinecone.py

Or run standalone to print all document IDs and a text preview:
    python rag_compensation_docs.py

Document categories
-------------------
    OFFER-DELAY       – Delay compensation tiers & offers
    OFFER-CANCEL      – Train cancellation rules & offers
    OFFER-MISSED-CON  – Missed connection rules
    OFFER-GOODWILL    – Goodwill gestures (below legal threshold)
    OFFER-TICKET-TYPE – Rules per ticket class (Sparpreis / Flexpreis / BahnCard)
    OFFER-ALT-TRANS   – Alternative transport reimbursement
    ESCALATION        – When & how to hand off to a human agent
    EXTRAORDINARY     – Circumstances that suspend compensation
    CLAIM-PROCESS     – Step-by-step claim filing guide
    HELPLINE          – Support hours, channels, callback rules
    ACCESSIBILITY     – Reduced-mobility & disability support
    LOST-LUGGAGE      – Lost / delayed luggage handling
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Schema reference (mirrors POLICY_DOCS in seed_pinecone.py)
# {
#   "id": str,
#   "language": "en" | "de" | "fr",
#   "document_type": str,   # see DOCUMENT_TYPES below
#   "category": str,        # new: OFFER-DELAY / ESCALATION / etc.
#   "region": "germany" | "eu",
#   "valid_from": "YYYY-MM-DD",
#   "valid_to":   "YYYY-MM-DD",
#   "source_url": str,
#   "confidence_score": float,
#   "text": str,
# }
# ---------------------------------------------------------------------------

COMPENSATION_DOCS: list[dict] = [

    # =========================================================================
    # OFFER-DELAY  –  Delay compensation tiers
    # =========================================================================

    {
        "id": "offer_delay_tiers_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "OFFER-DELAY",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/delay-tiers",
        "confidence_score": 0.99,
        "text": (
            "Document ID: OFFER-DELAY-001. Title: Delay Compensation Tiers. "
            "Category: Delay / Late Arrival. "
            "This document governs what the AI assistant must offer when a customer reports a train delay caused by the railway operator. "
            "TIER 1 – Delay under 30 minutes: "
            "No monetary compensation. Offer a sincere apology and provide a real-time status update. "
            "Do not offer a voucher unless the customer explicitly describes a significant personal impact. "
            "TIER 2 – Delay between 30 and 59 minutes: "
            "No statutory compensation under EU Regulation 1371/2007. "
            "Offer a goodwill apology message. "
            "If the customer describes a concrete negative impact (missed meeting, childcare, medical appointment), "
            "proactively suggest a goodwill voucher of 5 EUR as a gesture of goodwill. "
            "TIER 3 – Delay between 60 and 119 minutes: "
            "Statutory compensation of 25% of the ticket price applies (EU Reg. 1371/2007, Article 17). "
            "Offer the customer the choice between bank transfer (IBAN) or a DB voucher valid for 3 years. "
            "If the delay caused a missed connecting train, apply OFFER-MISSED-CON-001 in addition. "
            "TIER 4 – Delay between 120 and 179 minutes: "
            "Statutory compensation of 50% of the ticket price applies. "
            "Offer bank transfer or voucher. "
            "If the customer reports a missed appointment, financial loss, or high-value ticket, escalate to a human agent. "
            "TIER 5 – Delay of 180 minutes or more: "
            "Full refund of the unused portion of the ticket applies. "
            "If the customer has not yet travelled, they may cancel and receive a full refund under Article 16 of EU Reg. 1371/2007. "
            "Automatically escalate if the customer requests additional damages beyond the statutory refund. "
            "GENERAL RULE: The assistant must always state that the final compensation decision depends on verification by the support team. "
            "The assistant must never guarantee a specific payout amount without claim confirmation. "
            "Claims must be filed within 12 months of the delayed journey."
        ),
    },

    {
        "id": "offer_delay_tiers_de",
        "language": "de",
        "document_type": "compensation_rule",
        "category": "OFFER-DELAY",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://entschaedigungsregeln/verspaetungsstufen",
        "confidence_score": 0.99,
        "text": (
            "Dokument-ID: OFFER-DELAY-001-DE. Titel: Verspätungsentschädigungsstufen. "
            "Kategorie: Verspätung / Verspätete Ankunft. "
            "STUFE 1 – Verspätung unter 30 Minuten: Keine Entschädigung. Entschuldigung anbieten und aktuellen Status mitteilen. "
            "STUFE 2 – Verspätung 30–59 Minuten: Keine gesetzliche Entschädigung. "
            "Bei nachgewiesenem konkretem Nachteil (verpasster Termin, Kinderbetreuung, medizinischer Termin): "
            "Kulanzgutschein von 5 EUR vorschlagen. "
            "STUFE 3 – Verspätung 60–119 Minuten: Gesetzlicher Anspruch auf 25 % des Fahrpreises (EU-VO 1371/2007, Art. 17). "
            "Wahl zwischen Banküberweisung (IBAN) oder DB-Gutschein (3 Jahre gültig) anbieten. "
            "Bei verpasstem Anschluss: OFFER-MISSED-CON-001 zusätzlich anwenden. "
            "STUFE 4 – Verspätung 120–179 Minuten: Gesetzlicher Anspruch auf 50 % des Fahrpreises. "
            "Bei verpasstem wichtigen Termin oder hohem Ticketpreis: an menschlichen Agenten eskalieren. "
            "STUFE 5 – Verspätung ab 180 Minuten: Vollständige Rückerstattung des nicht genutzten Fahrtanteils. "
            "Wenn die Reise noch nicht angetreten wurde: vollständige Rückerstattung nach Art. 16 EU-VO 1371/2007. "
            "Bei Forderung weitergehender Schadensersatzansprüche: eskalieren. "
            "ALLGEMEINE REGEL: Der Assistent muss stets darauf hinweisen, dass die endgültige Entschädigungsentscheidung "
            "durch das Support-Team verifiziert werden muss. Antragsfrist: 12 Monate nach der verspäteten Fahrt."
        ),
    },

    # =========================================================================
    # OFFER-CANCEL  –  Train cancellation
    # =========================================================================

    {
        "id": "offer_cancel_rules_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "OFFER-CANCEL",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/cancellation",
        "confidence_score": 0.98,
        "text": (
            "Document ID: OFFER-CANCEL-001. Title: Train Cancellation Compensation Rules. "
            "Category: Train Cancellation. "
            "If a customer reports that their train was cancelled, the following rules apply. "
            "OPTION A – Rerouting: The customer is entitled to re-routing on the next available train at no additional cost. "
            "Seat reservation fees for the new train are waived. Offer to look up alternative connections immediately. "
            "OPTION B – Full refund: If the customer chooses not to travel due to the cancellation, "
            "they are entitled to a full refund of the ticket price regardless of ticket type (including non-refundable Sparpreis). "
            "The refund applies to the entire trip if a connection was missed as a result. "
            "OPTION C – Intermediate stop refund: If the passenger is already on a journey and the train terminates early, "
            "they receive a full refund for the uncompleted portion of the journey, "
            "plus DB covers reasonable costs of onward travel (taxi, bus) up to a cap verified by the support team. "
            "GOODWILL: For cancellations notified less than 30 minutes before departure, "
            "offer a goodwill voucher of 10 EUR on top of statutory rights. "
            "ESCALATION: Escalate if the customer reports consequential losses (hotel, flights, events). "
            "Always confirm: final compensation depends on verification by the support team."
        ),
    },

    {
        "id": "offer_cancel_rules_de",
        "language": "de",
        "document_type": "compensation_rule",
        "category": "OFFER-CANCEL",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://entschaedigungsregeln/zugsausfall",
        "confidence_score": 0.98,
        "text": (
            "Dokument-ID: OFFER-CANCEL-001-DE. Titel: Regelungen bei Zugausfall. "
            "Bei Zugausfall stehen dem Fahrgast folgende Optionen zu: "
            "OPTION A – Umleitung: Kostenlose Weiterfahrt mit dem nächsten verfügbaren Zug. Reservierungsgebühren werden erlassen. "
            "OPTION B – Vollrückerstattung: Wenn der Fahrgast die Reise nicht antritt oder abbricht, "
            "erhält er den vollständigen Fahrpreis erstattet – auch bei Sparpreis-Tickets. "
            "Die Rückerstattung gilt für die gesamte Reise, wenn ein Anschluss verpasst wurde. "
            "OPTION C – Rückerstattung für nicht genutzte Teilstrecke plus angemessene Kosten für Weiterreise (Taxi, Bus). "
            "KULANZ: Bei Ausfall weniger als 30 Minuten vor Abfahrt: Kulanzgutschein von 10 EUR zusätzlich. "
            "ESKALATION: Bei Folgekosten (Hotel, Flug, Veranstaltung) an menschlichen Agenten eskalieren. "
            "Endentscheidung liegt beim Support-Team."
        ),
    },

    # =========================================================================
    # OFFER-MISSED-CON  –  Missed connection
    # =========================================================================

    {
        "id": "offer_missed_connection_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "OFFER-MISSED-CON",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/missed-connection",
        "confidence_score": 0.97,
        "text": (
            "Document ID: OFFER-MISSED-CON-001. Title: Missed Connection Compensation Rules. "
            "Category: Missed Connection. "
            "A missed connection occurs when a passenger fails to board a connecting train "
            "because of a delay or cancellation of an earlier DB service on the same booking. "
            "RULE 1: If the connection is on the same ticket/booking and the delay causing the miss is ≥ 1 minute, "
            "DB is responsible and re-routing or full refund applies (see OFFER-CANCEL-001). "
            "RULE 2: Compensation calculation includes the full journey delay at the final destination, "
            "not just the delay of the first train. "
            "RULE 3 – Waiting at the connection station: If the next connecting train departs within 60 minutes, "
            "advise the customer to wait and board. Seat reservation is automatically transferred where possible. "
            "RULE 4 – Waiting time over 60 minutes: Offer a refreshment voucher (up to 10 EUR) for the waiting period. "
            "This is a goodwill gesture and subject to supply at the station. "
            "RULE 5 – Overnight stay: If the missed connection results in no feasible onward travel on the same day, "
            "DB covers the cost of one night's hotel accommodation (reasonable rate, verified by support team) "
            "and meals up to 15 EUR. Customer must keep receipts. "
            "ESCALATION: Escalate if the customer requests hotel reimbursement, "
            "or if the total journey delay exceeds 3 hours. "
            "Always confirm: final compensation depends on verification by the support team."
        ),
    },

    # =========================================================================
    # OFFER-GOODWILL  –  Goodwill gestures (below legal compensation threshold)
    # =========================================================================

    {
        "id": "offer_goodwill_rules_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "OFFER-GOODWILL",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/goodwill",
        "confidence_score": 0.95,
        "text": (
            "Document ID: OFFER-GOODWILL-001. Title: Goodwill Gesture Rules. "
            "Category: Goodwill / Below Statutory Threshold. "
            "Goodwill gestures are discretionary offers made to customers when statutory compensation does not apply "
            "but the customer has experienced a genuine inconvenience. "
            "TRIGGER 1 – Delay under 60 minutes with documented impact: "
            "Offer a goodwill voucher of 5 EUR if the customer explicitly describes personal inconvenience "
            "(missed appointment, childcare, medical, work meeting). Do not offer proactively for minor delays. "
            "TRIGGER 2 – Train cancellation notified less than 30 minutes before scheduled departure: "
            "Offer a 10 EUR goodwill voucher in addition to statutory cancellation rights. "
            "TRIGGER 3 – Repeated delays on the same route within 30 days: "
            "If the customer provides evidence of recurring delays on the same route, "
            "escalate to a human agent who may authorise a goodwill voucher of up to 25 EUR. "
            "TRIGGER 4 – Customer expresses significant distress or frustration: "
            "Use empathetic language and offer a 5 EUR voucher as a token of goodwill. "
            "Do not offer more than 5 EUR without human agent authorisation. "
            "LIMITS: The assistant may suggest goodwill vouchers but cannot authorise amounts above 10 EUR. "
            "Amounts above 10 EUR require human agent approval. "
            "Vouchers are valid for 1 year and redeemable on any DB service. "
            "RECORD: All goodwill offers must be noted in the ticket/case log. "
            "Always confirm: goodwill gestures are discretionary and require final approval from the support team."
        ),
    },

    {
        "id": "offer_goodwill_rules_de",
        "language": "de",
        "document_type": "compensation_rule",
        "category": "OFFER-GOODWILL",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://entschaedigungsregeln/kulanz",
        "confidence_score": 0.95,
        "text": (
            "Dokument-ID: OFFER-GOODWILL-001-DE. Titel: Kulanzregelungen. "
            "Kulanzleistungen werden angeboten, wenn kein gesetzlicher Entschädigungsanspruch besteht, "
            "der Fahrgast aber eine echte Unannehmlichkeit erlitten hat. "
            "AUSLÖSER 1 – Verspätung unter 60 Minuten mit nachgewiesenem Nachteil: 5-EUR-Kulanzgutschein anbieten. "
            "AUSLÖSER 2 – Zugausfall weniger als 30 Minuten vor Abfahrt: 10-EUR-Kulanzgutschein zusätzlich zu gesetzlichen Rechten. "
            "AUSLÖSER 3 – Wiederholte Verspätungen auf derselben Strecke innerhalb von 30 Tagen: "
            "An menschlichen Agenten eskalieren; Kulanzgutschein bis 25 EUR möglich. "
            "AUSLÖSER 4 – Starke Frustration oder Verzweiflung des Fahrgastes: 5-EUR-Gutschein als Geste anbieten. "
            "GRENZEN: Der Assistent darf Kulanzgutscheine bis 10 EUR vorschlagen; "
            "höhere Beträge erfordern Genehmigung durch einen menschlichen Agenten. "
            "Gutscheine sind 1 Jahr gültig. Alle Kulanzangebote müssen im Ticketprotokoll vermerkt werden. "
            "Endgültige Kulanzentscheidung liegt beim Support-Team."
        ),
    },

    # =========================================================================
    # OFFER-TICKET-TYPE  –  Compensation rules by ticket type
    # =========================================================================

    {
        "id": "offer_ticket_type_rules_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "OFFER-TICKET-TYPE",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/ticket-types",
        "confidence_score": 0.96,
        "text": (
            "Document ID: OFFER-TICKET-TYPE-001. Title: Ticket Type Compensation Rules. "
            "Category: Ticket Type / Fare Class. "
            "Compensation and refund rules vary by ticket type. "
            "SPARPREIS (discounted, non-flexible): "
            "Normally non-refundable for voluntary cancellations. "
            "However, if the journey is affected by a delay ≥ 60 min or cancellation, full compensation applies under EU Reg. 1371/2007. "
            "The non-refundable clause does not override statutory passenger rights. "
            "FLEXPREIS (flexible, full-fare): "
            "Fully refundable for voluntary cancellations up to departure. "
            "For delays ≥ 60 min: 25% refund; ≥ 120 min: 50% refund; ≥ 180 min or cancellation: full refund. "
            "BAHNCARD 25 / 50 HOLDER: "
            "Compensation is calculated on the discounted ticket price actually paid, not the base Flexpreis price. "
            "A BahnCard holder whose 60-min delay gives 25% of the BahnCard-discounted fare. "
            "BAHNCARD 100: "
            "Compensation for a BahnCard 100 holder is a proportional daily refund of the monthly/annual fee "
            "for days with documented significant delays. Escalate BahnCard 100 claims to a human agent. "
            "GRUPPENREISE / GROUP TICKETS: "
            "Compensation is calculated per-passenger on the pro-rata ticket price. "
            "The group organiser must file the claim on behalf of the group. "
            "SEAT RESERVATION FEE (4.50 EUR): "
            "The seat reservation fee is refunded separately if the reserved seat was unavailable due to the delay or cancellation. "
            "Always confirm: ticket type is verified by the support team against booking records."
        ),
    },

    # =========================================================================
    # OFFER-ALT-TRANS  –  Alternative transport reimbursement
    # =========================================================================

    {
        "id": "offer_alt_transport_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "OFFER-ALT-TRANS",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/alternative-transport",
        "confidence_score": 0.96,
        "text": (
            "Document ID: OFFER-ALT-TRANS-001. Title: Alternative Transport Reimbursement Rules. "
            "Category: Alternative Transport. "
            "If a train is cancelled or delayed so severely that a passenger arranges their own alternative transport, "
            "the following reimbursement rules apply. "
            "ELIGIBLE ALTERNATIVES: Taxi, rideshare, rental car, bus, or another rail operator's ticket "
            "taken as a direct result of the DB service failure. "
            "REIMBURSEMENT LIMIT – Taxi/rideshare: Reimbursed up to 50 EUR for journeys within the same urban area. "
            "For intercity taxis, the cap is 80 EUR. Amounts above the cap require human agent approval. "
            "REIMBURSEMENT LIMIT – Bus or other rail: Fully reimbursed if the ticket price is reasonable. "
            "DOCUMENTATION: Customer must provide: (a) original DB ticket showing the affected journey, "
            "(b) receipt/invoice for the alternative transport, (c) departure time evidence of the DB delay or cancellation. "
            "Without documentation, the claim cannot be processed. "
            "TIMING: The alternative transport must have been taken on the same day as the affected DB service. "
            "Next-day travel is not covered unless a hotel was already approved under OFFER-MISSED-CON-001. "
            "ESCALATION: Claims for alternative transport exceeding 80 EUR must be escalated to a human agent. "
            "Always confirm: reimbursement is subject to verification of documentation by the support team."
        ),
    },

    # =========================================================================
    # EXTRAORDINARY  –  Circumstances suspending compensation
    # =========================================================================

    {
        "id": "extraordinary_circumstances_en",
        "language": "en",
        "document_type": "compensation_rule",
        "category": "EXTRAORDINARY",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://compensation-rules/extraordinary-circumstances",
        "confidence_score": 0.98,
        "text": (
            "Document ID: EXTRAORDINARY-001. Title: Extraordinary Circumstances – Compensation Exclusions. "
            "Category: Compensation Exclusions. "
            "Under EU Regulation 1371/2007, compensation is not owed if the delay or cancellation was caused by: "
            "(1) Severe weather events: storms, flooding, heavy snowfall, ice storms, or extreme temperatures "
            "that could not have been avoided even with all reasonable precautions. "
            "(2) Natural disasters: earthquakes, landslides, or other acts of nature. "
            "(3) Third-party obstructions: persons on the track, animal strikes, or vehicle collisions at level crossings "
            "outside the railway operator's control. "
            "(4) Industrial action / strikes: Official strikes by third-party workers (e.g., air traffic control). "
            "Note: DB's own staff strikes DO still entitle passengers to compensation. "
            "(5) Security incidents: Police-ordered service suspensions, bomb threats, or terrorism. "
            "(6) Infrastructure failure beyond DB's control: failures on non-DB managed rail networks "
            "where DB has no maintenance responsibility. "
            "IMPORTANT – What still qualifies despite extraordinary circumstances: "
            "Even in extraordinary circumstances, if DB failed to inform passengers before ticket purchase "
            "or did not provide timely journey information at the station, partial goodwill compensation may be offered. "
            "ASSISTANT RULE: If the customer reports a delay caused by weather or a third party, "
            "the assistant must acknowledge the difficulty, explain the extraordinary circumstances clause, "
            "and offer to check whether any goodwill compensation is available. "
            "Do NOT immediately deny compensation without checking the specific incident with the support team. "
            "Always confirm: the final determination of extraordinary circumstances is made by the support team."
        ),
    },

    {
        "id": "extraordinary_circumstances_de",
        "language": "de",
        "document_type": "compensation_rule",
        "category": "EXTRAORDINARY",
        "region": "eu",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://entschaedigungsregeln/aussergewoehnliche-umstaende",
        "confidence_score": 0.98,
        "text": (
            "Dokument-ID: EXTRAORDINARY-001-DE. Titel: Außergewöhnliche Umstände – Entschädigungsausschlüsse. "
            "Nach EU-VO 1371/2007 besteht kein Entschädigungsanspruch bei: "
            "(1) Extremwetterereignissen: Stürmen, Überschwemmungen, Schneefall, Eis, extremen Temperaturen. "
            "(2) Naturkatastrophen: Erdbeben, Erdrutsche. "
            "(3) Fremdverschulden: Personen im Gleis, Wildunfälle, Kollisionen an Bahnübergängen außerhalb der DB-Kontrolle. "
            "(4) Streik Dritter: Streiks von Mitarbeitern anderer Unternehmen (z.B. Fluglotsen). "
            "Hinweis: DB-eigene Streiks berechtigen weiterhin zur Entschädigung. "
            "(5) Sicherheitsvorfälle: Polizeilich angeordnete Sperrungen, Bombendrohungen, Terrorismus. "
            "(6) Infrastrukturausfälle außerhalb des DB-Verantwortungsbereichs. "
            "WICHTIG: Auch bei außergewöhnlichen Umständen kann eine Kulanzentschädigung angeboten werden, "
            "wenn DB die Fahrgäste nicht rechtzeitig informiert hat. "
            "ASSISTENTENREGEL: Nicht sofort ablehnen – stets beim Support-Team nachfragen, "
            "ob im konkreten Fall eine Kulanzleistung möglich ist."
        ),
    },

    # =========================================================================
    # CLAIM-PROCESS  –  Step-by-step claim filing guide
    # =========================================================================

    {
        "id": "claim_process_guide_en",
        "language": "en",
        "document_type": "claim_process",
        "category": "CLAIM-PROCESS",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://claim-process/guide",
        "confidence_score": 0.97,
        "text": (
            "Document ID: CLAIM-PROCESS-001. Title: Compensation Claim Filing Guide. "
            "Category: Claim Process. "
            "The assistant guides the customer through the following steps to file a compensation claim. "
            "STEP 1 – Collect required information: "
            "Train number (e.g., ICE 572, RE 50), station name, planned departure time, actual departure time (or 'not departed'), "
            "whether the trip was started or not, ticket price in EUR, preferred refund method (bank transfer or voucher). "
            "STEP 2 – If refund by bank transfer: request IBAN. Display only the last 4 digits in all confirmations. "
            "If refund by voucher: confirm mailing address. "
            "STEP 3 – Calculate compensation using the following logic: "
            "  delay < 60 min → 0% (no statutory compensation, check goodwill rules OFFER-GOODWILL-001). "
            "  60–119 min → 25% of ticket price. "
            "  120+ min  → 50% of ticket price. "
            "  Cancellation / trip not started → 100% refund. "
            "STEP 4 – Submit the claim and display the claim reference number to the customer. "
            "STEP 5 – Inform the customer of processing timelines: "
            "  Bank transfer: 5–10 business days after approval. "
            "  Voucher: dispatched within 3–5 business days by post. "
            "STEP 6 – Advise the customer to retain their original ticket and any receipts (alternative transport, hotel, meals) "
            "as the support team may request these during verification. "
            "IMPORTANT: Claims must be filed within 12 months of the date of the delayed or cancelled journey. "
            "The assistant must always state that the final decision rests with the support team."
        ),
    },

    {
        "id": "claim_process_guide_de",
        "language": "de",
        "document_type": "claim_process",
        "category": "CLAIM-PROCESS",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://antragsablauf/leitfaden",
        "confidence_score": 0.97,
        "text": (
            "Dokument-ID: CLAIM-PROCESS-001-DE. Titel: Leitfaden zur Entschädigungsantragstellung. "
            "SCHRITT 1 – Erforderliche Angaben sammeln: "
            "Zugnummer, Bahnhof, planmäßige Abfahrtszeit, tatsächliche Abfahrtszeit (oder 'nicht abgefahren'), "
            "ob die Fahrt angetreten wurde, Ticketpreis in EUR, bevorzugte Erstattungsmethode. "
            "SCHRITT 2 – Erstattung per Banküberweisung: IBAN erfragen; nur die letzten 4 Ziffern anzeigen. "
            "Erstattung per Gutschein: Postanschrift bestätigen. "
            "SCHRITT 3 – Entschädigung berechnen: "
            "  unter 60 Min → 0% (keine gesetzliche Entschädigung; Kulanzregeln OFFER-GOODWILL-001 prüfen). "
            "  60–119 Min  → 25% des Fahrpreises. "
            "  ab 120 Min  → 50% des Fahrpreises. "
            "  Zugausfall / Fahrt nicht angetreten → 100% Rückerstattung. "
            "SCHRITT 4 – Antrag einreichen und Referenznummer anzeigen. "
            "SCHRITT 5 – Bearbeitungszeiten: Banküberweisung 5–10 Werktage; Gutscheinversand 3–5 Werktage. "
            "SCHRITT 6 – Originalfahrkarte und Belege (Alternative, Hotel, Verpflegung) aufbewahren. "
            "WICHTIG: Anträge müssen innerhalb von 12 Monaten eingereicht werden. "
            "Endentscheidung liegt beim Support-Team."
        ),
    },

    # =========================================================================
    # ESCALATION  –  When & how to escalate to a human agent
    # =========================================================================

    {
        "id": "escalation_triggers_en",
        "language": "en",
        "document_type": "internal_sop",
        "category": "ESCALATION",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/escalation-triggers",
        "confidence_score": 0.99,
        "text": (
            "Document ID: ESCALATION-001. Title: Human Agent Escalation Triggers. "
            "Category: Escalation / Human Handoff. "
            "The AI assistant MUST escalate to a human agent in the following situations. "
            "MANDATORY ESCALATION: "
            "(1) Customer reports total journey delay ≥ 180 minutes AND requests compensation beyond statutory refund. "
            "(2) Customer reports consequential financial loss: hotel costs, flight rebooking, cancelled events, loss of income. "
            "(3) Customer explicitly requests to speak with a human agent or supervisor. "
            "(4) Customer expresses sustained distress, uses urgent language ('emergency', 'urgent', 'crisis'), or mentions a medical situation. "
            "(5) Customer dispute: Customer disagrees with compensation calculation or has already filed and been denied. "
            "(6) BahnCard 100 compensation claim (pro-rata fee reimbursement). "
            "(7) Group ticket claim involving more than 5 passengers. "
            "(8) Alternative transport reimbursement claims exceeding 80 EUR. "
            "(9) Recurring delay complaint on the same route with documented history. "
            "(10) Legal threat or mention of regulatory complaint (Bundesnetzagentur, Verbraucherzentrale). "
            "DISCRETIONARY ESCALATION (assistant may decide): "
            "(A) Customer has a disability or reduced mobility and the standard flow does not meet their needs. "
            "(B) The assistant is uncertain about the correct compensation rule for an unusual case. "
            "(C) The automated compensation calculation cannot be confirmed due to missing data. "
            "HOW TO ESCALATE: "
            "The assistant uses the human_handoff_tool. It must summarise the case clearly: "
            "train number, delay duration, customer concern, compensation discussed so far, and reason for escalation. "
            "The assistant must tell the customer: "
            "'I am transferring you to a specialist who can assist further. Your reference number is [ID]. "
            "Expected wait time is typically under 5 minutes during business hours.' "
            "Business hours: Monday–Friday 07:00–21:00, Saturday–Sunday 08:00–20:00 (CET)."
        ),
    },

    {
        "id": "escalation_triggers_de",
        "language": "de",
        "document_type": "internal_sop",
        "category": "ESCALATION",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/eskalationsausloeser",
        "confidence_score": 0.99,
        "text": (
            "Dokument-ID: ESCALATION-001-DE. Titel: Eskalationsauslöser für menschliche Agenten. "
            "PFLICHTESKALATION: "
            "(1) Gesamtverspätung ≥ 180 Min. und Forderung über gesetzliche Erstattung hinaus. "
            "(2) Folgekosten: Hotel, Umbuchung, verlorene Veranstaltungen, Einkommensverlust. "
            "(3) Ausdrücklicher Wunsch nach menschlichem Ansprechpartner oder Vorgesetztem. "
            "(4) Anhaltende Verzweiflung, Dringlichkeitssignale ('Notfall', 'dringend', 'Krise') oder medizinische Situation. "
            "(5) Kundenstreit: Widerspruch gegen Entschädigungsberechnung oder frühere Ablehnung. "
            "(6) BahnCard-100-Entschädigungsanspruch. "
            "(7) Gruppenreiseantrag mit mehr als 5 Personen. "
            "(8) Alternative-Transport-Erstattung über 80 EUR. "
            "(9) Wiederholte Verspätungsbeschwerde auf derselben Strecke. "
            "(10) Rechtliche Drohung oder Erwähnung einer Beschwerde bei Bundesnetzagentur / Verbraucherzentrale. "
            "ERMESSENSESKALATION: Behinderung/eingeschränkte Mobilität; Unsicherheit bei Sonderfällen; fehlende Daten. "
            "VORGEHENSWEISE: Human-Handoff-Tool verwenden. Fallzusammenfassung inkl. Zugnummer, Verspätung, "
            "bisherige Entschädigung und Eskalationsgrund. Dem Kunden mitteilen: "
            "'Ich verbinde Sie jetzt mit einem Spezialisten. Referenznummer: [ID]. Wartezeit: i.d.R. unter 5 Minuten.' "
            "Servicezeiten: Mo–Fr 07:00–21:00 Uhr, Sa–So 08:00–20:00 Uhr (MEZ)."
        ),
    },

    {
        "id": "escalation_emotional_en",
        "language": "en",
        "document_type": "internal_sop",
        "category": "ESCALATION",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/emotional-customer-handling",
        "confidence_score": 0.94,
        "text": (
            "Document ID: ESCALATION-002. Title: Emotional Customer Handling Protocol. "
            "Category: Escalation / Emotional Support. "
            "When a customer expresses significant frustration, anger, or distress, the assistant follows this protocol. "
            "STEP 1 – Acknowledge: Use empathetic language before any procedural information. "
            "Example: 'I'm really sorry to hear about this experience. That sounds very frustrating, especially if you had important plans.' "
            "Do not immediately jump to compensation rules. "
            "STEP 2 – Validate: Confirm that the customer's frustration is understood and justified. "
            "STEP 3 – Offer concrete help: Offer the most relevant option first (re-routing, claim filing, human escalation). "
            "STEP 4 – Do not argue or correct aggressively: If the customer is factually wrong about their rights, "
            "gently correct them while maintaining empathy: 'I understand why you might expect that. "
            "Let me explain exactly what I can arrange for you.' "
            "STEP 5 – Goodwill gesture: In emotionally charged situations, proactively offer a goodwill voucher "
            "within the 5–10 EUR range (see OFFER-GOODWILL-001) as a token of goodwill, without the customer having to ask. "
            "STEP 6 – Escalate if emotion remains high: If the customer remains distressed after two response cycles, "
            "escalate to a human agent using the handoff tool. Do not continue the automated loop. "
            "TONE RULE: The assistant must never use dismissive phrases like 'I understand the rules state...' "
            "or 'Unfortunately there is nothing I can do.' Always frame limitations as 'let me see what I can arrange.'"
        ),
    },

    # =========================================================================
    # HELPLINE  –  Support hours, channels, callback
    # =========================================================================

    {
        "id": "helpline_support_info_en",
        "language": "en",
        "document_type": "helpline",
        "category": "HELPLINE",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://helpline/contact-channels",
        "confidence_score": 0.93,
        "text": (
            "Document ID: HELPLINE-001. Title: Helpline Contact Channels & Support Hours. "
            "Category: Helpline / Support Channels. "
            "DB Customer Service is available through the following channels. "
            "PHONE: DB Service Center at 030 2970 (German landline rate). "
            "Hours: Monday–Friday 07:00–22:00, Saturday–Sunday 08:00–22:00 (CET). "
            "CHAT (this assistant): Available 24 / 7. Handles delays, claims, routing. "
            "Escalation to human agent available Monday–Friday 07:00–21:00, Saturday–Sunday 08:00–20:00 (CET). "
            "Outside hours: the assistant can file the case and schedule a callback. "
            "EMAIL/ONLINE FORM: bahn.de/kontakt. Response within 3–5 business days. "
            "DB REISEZENTRUM (Travel Centre): Available in all major stations. "
            "Can process compensation claims directly. "
            "DB NAVIGATOR APP: Real-time train status and in-app claim submission available. "
            "CALLBACK SCHEDULING: "
            "If the customer requests a callback, the assistant must collect: preferred callback number, "
            "best time window (morning / afternoon / evening), and a brief description of the issue. "
            "Confirm: 'I have registered your callback request. A DB colleague will call you within [window].' "
            "SOCIAL MEDIA: @DB_Bahn on Twitter/X and Facebook Messenger. "
            "Note: Social media agents cannot process compensation claims directly; "
            "they redirect to phone or online form. "
            "LANGUAGE: German and English service guaranteed. Other languages on a best-effort basis."
        ),
    },

    {
        "id": "helpline_support_info_de",
        "language": "de",
        "document_type": "helpline",
        "category": "HELPLINE",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://helpline/kontaktkanaele",
        "confidence_score": 0.93,
        "text": (
            "Dokument-ID: HELPLINE-001-DE. Titel: Helpline-Kontaktkanäle und Servicezeiten. "
            "TELEFON: DB Service Center 030 2970 (zum Ortstarif). "
            "Servicezeiten: Mo–Fr 07:00–22:00 Uhr, Sa–So 08:00–22:00 Uhr (MEZ). "
            "CHAT (dieser Assistent): 24/7 verfügbar für Verspätungen, Entschädigungen und Routenplanung. "
            "Weiterleitung an menschlichen Agenten: Mo–Fr 07:00–21:00, Sa–So 08:00–20:00 Uhr. "
            "Außerhalb der Zeiten: Fall anlegen und Rückruf vereinbaren. "
            "E-MAIL / ONLINE-FORMULAR: bahn.de/kontakt. Antwort innerhalb von 3–5 Werktagen. "
            "DB REISEZENTRUM: In allen größeren Bahnhöfen. Direkte Antragsbearbeitung möglich. "
            "DB NAVIGATOR APP: Echtzeit-Zugstatus und Entschädigungsanträge in der App. "
            "RÜCKRUF: Rückrufwunsch mit Telefonnummer, bevorzugtem Zeitfenster und Beschreibung des Anliegens aufnehmen. "
            "Bestätigung: 'Ihr Rückrufwunsch wurde registriert. Ein DB-Mitarbeiter meldet sich innerhalb von [Fenster].' "
            "SOCIAL MEDIA: @DB_Bahn auf Twitter/X und Facebook Messenger – keine direkte Antragsbearbeitung."
        ),
    },

    # =========================================================================
    # ACCESSIBILITY  –  Reduced mobility & disability support
    # =========================================================================

    {
        "id": "accessibility_support_en",
        "language": "en",
        "document_type": "accessibility",
        "category": "ACCESSIBILITY",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/accessibility",
        "confidence_score": 0.95,
        "text": (
            "Document ID: ACCESSIBILITY-001. Title: Accessibility & Reduced Mobility Support Rules. "
            "Category: Accessibility / Reduced Mobility. "
            "DB provides specific assistance for passengers with disabilities or reduced mobility. "
            "ADVANCE BOOKING: Mobility assistance must be booked at least 20 hours before travel "
            "via db-barrierefrei.de or +49 30 65 21 28 88. "
            "ON ARRIVAL: Station staff are available to assist with boarding and alighting. "
            "If assistance was pre-booked and was not provided, this constitutes a service failure. "
            "COMPENSATION FOR SERVICE FAILURE – ACCESSIBILITY: "
            "If pre-booked mobility assistance was not provided, "
            "the passenger is entitled to compensation equivalent to a 25% refund of the ticket price, "
            "regardless of whether a delay occurred. "
            "ESCALATION: All accessibility-related compensation claims and complaints must be escalated "
            "to a human agent immediately. The assistant must NOT attempt to resolve these autonomously. "
            "RAMP / LIFT FAILURE: If a station lift or ramp was out of service and prevented the passenger from boarding, "
            "this is treated as a DB service failure. Compensation rules under OFFER-CANCEL-001 apply. "
            "HEARING / VISUAL IMPAIRMENT: The assistant is available via text chat. "
            "For customers with hearing impairment needing sign language support, escalate to a specialist agent. "
            "TONE: Use plain language, avoid jargon, and offer to repeat information in a simplified format. "
            "Patience is paramount. Never rush an accessibility-related interaction."
        ),
    },

    # =========================================================================
    # LOST-LUGGAGE  –  Lost or delayed luggage
    # =========================================================================

    {
        "id": "lost_luggage_rules_en",
        "language": "en",
        "document_type": "luggage",
        "category": "LOST-LUGGAGE",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://sop/lost-luggage",
        "confidence_score": 0.92,
        "text": (
            "Document ID: LOST-LUGGAGE-001. Title: Lost and Delayed Luggage Handling Rules. "
            "Category: Luggage / Lost Property. "
            "DB's liability for passenger luggage is governed by EU Regulation 1371/2007 and CIV. "
            "LOST PROPERTY AT A STATION: "
            "Direct the customer to the DB Fundservice (Lost Property Service) at +49 900 1 990599 "
            "or online at bahn.de/fundservice. "
            "Items are held for 3 months at the station's lost property office. "
            "LUGGAGE LEFT ON TRAIN: "
            "Ask for: train number, seat coach/number, departure and destination station, and description of the item. "
            "File a report via the DB Fundservice system. "
            "Notify the customer that recovery cannot be guaranteed but DB will attempt to locate the item within 48 hours. "
            "LUGGAGE DAMAGED IN TRANSIT (Reisegepäck/DB Gepäck service): "
            "If luggage was checked in via the DB Gepäck (luggage shipping) service, "
            "damage claims must be filed within 7 days of receipt with photographic evidence. "
            "Compensation is capped at 1,000 EUR per item unless a higher value was declared at check-in. "
            "HAND LUGGAGE: DB is not liable for hand luggage kept with the passenger. "
            "ESCALATION: If the item is high-value (over 200 EUR estimated value) or the customer reports it missing "
            "more than 48 hours after travel, escalate to a human agent for specialist follow-up. "
            "Always confirm: luggage recovery and damage claims are handled by a specialist team and may take up to 14 days."
        ),
    },

    # =========================================================================
    # REFUND-METHOD-DETAIL  –  Detailed refund method guidance (supplements existing)
    # =========================================================================

    {
        "id": "refund_method_detail_en",
        "language": "en",
        "document_type": "refund",
        "category": "REFUND-METHOD",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://refund-methods/detail",
        "confidence_score": 0.97,
        "text": (
            "Document ID: REFUND-METHOD-001. Title: Refund Method Rules & Processing Details. "
            "Category: Refund Method. "
            "BANK TRANSFER (Banküberweisung): "
            "Customer provides IBAN. The assistant displays only the last 4 digits in all confirmations (PII rule). "
            "Processing time: 5–10 business days after claim approval. "
            "Only EU/EEA IBANs are accepted. Non-EU bank accounts must be handled by a human agent. "
            "DB VOUCHER (Gutschein): "
            "Voucher is valid for 3 years from the date of issue. "
            "Redeemable for any DB ticket purchased via bahn.de, DB Navigator app, or at DB Reisezentrum. "
            "Vouchers cannot be exchanged for cash. "
            "Dispatch: within 3–5 business days by post, or immediately as a digital code if the customer has a DB account. "
            "For digital dispatch, confirm the customer's registered email address. "
            "RECOMMENDATION RULE: "
            "If the compensation amount is under 25 EUR, the assistant may suggest the voucher as the faster option. "
            "If the amount is 25 EUR or more, present both options neutrally and let the customer decide. "
            "PARTIAL REFUNDS: For Flexpreis tickets voluntarily cancelled before departure, "
            "a handling fee of 17.50 EUR applies unless the journey was affected by a delay or cancellation. "
            "FAILED BANK TRANSFERS: If the first bank transfer attempt fails, "
            "the customer is contacted to verify their IBAN and the attempt is retried once. "
            "After two failed attempts, a voucher is issued instead. Escalate if the customer objects. "
            "All refund decisions are subject to final verification by the support team."
        ),
    },

    {
        "id": "refund_method_detail_de",
        "language": "de",
        "document_type": "refund",
        "category": "REFUND-METHOD",
        "region": "germany",
        "valid_from": "2026-01-01",
        "valid_to": "2099-12-31",
        "source_url": "internal://erstattungsmethoden/detail",
        "confidence_score": 0.97,
        "text": (
            "Dokument-ID: REFUND-METHOD-001-DE. Titel: Erstattungsmethoden – Details und Verarbeitungsregeln. "
            "BANKÜBERWEISUNG: IBAN erforderlich. Im Chat und auf Belegen werden nur die letzten 4 Ziffern angezeigt (Datenschutzvorgabe). "
            "Bearbeitungszeit: 5–10 Werktage nach Genehmigung. Nur EU/EWR-IBANs werden akzeptiert; "
            "Nicht-EU-Konten müssen von einem menschlichen Agenten bearbeitet werden. "
            "DB-GUTSCHEIN: Gültig 3 Jahre ab Ausstellungsdatum. "
            "Einlösbar für alle DB-Tickets über bahn.de, DB Navigator oder DB Reisezentrum. "
            "Keine Barauszahlung. Versand per Post: 3–5 Werktage; als digitaler Code sofort (bei vorhandenem DB-Konto). "
            "EMPFEHLUNGSREGEL: Unter 25 EUR: Gutschein als schnellere Option vorschlagen. "
            "Ab 25 EUR: beide Optionen neutral anbieten. "
            "TEILERSTATTUNG: Bei freiwilliger Stornierung von Flexpreis-Tickets fällt eine Bearbeitungsgebühr von 17,50 EUR an, "
            "sofern kein Verspätungs- oder Ausfallereignis vorliegt. "
            "GESCHEITERTE ÜBERWEISUNG: Erneuter Versuch nach IBAN-Korrektur; nach zwei Fehlversuchen wird Gutschein ausgestellt. "
            "Bei Widerspruch eskalieren. Alle Erstattungsentscheidungen bedürfen der abschließenden Prüfung durch das Support-Team."
        ),
    },

]


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\nDeBian Synthetic RAG Compensation Documents  ({len(COMPENSATION_DOCS)} total)\n")
    print(f"{'ID':<45} {'LANG':<5} {'CATEGORY':<22} {'TYPE'}")
    print("-" * 110)
    for doc in COMPENSATION_DOCS:
        print(
            f"{doc['id']:<45} {doc['language']:<5} "
            f"{doc.get('category', 'N/A'):<22} {doc['document_type']}"
        )
    print()
    print("To seed into Pinecone, add to seed_pinecone.py:")
    print("  from rag_compensation_docs import COMPENSATION_DOCS")
    print("  POLICY_DOCS.extend(COMPENSATION_DOCS)")
