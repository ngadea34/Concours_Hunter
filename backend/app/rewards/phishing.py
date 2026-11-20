"""Détection de faux messages de gain (score 0..100, 100 = très suspect)."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..i18n.geo import norm

FREE_MAIL = re.compile(r"@(gmail|yahoo|hotmail|outlook|live|gmx|aol|proton(mail)?|mail\.ru|yandex|icloud|laposte|orange|free|sfr)\.", re.I)
RULES: list[tuple[str, str, int]] = [
    (r"(frais|fees?|taxes?|douane|customs|livraison|shipping|dossier|processing).{0,60}(payer|regler|verser|pay|\d+[.,]?\d*\s?(€|eur|\$))", "Paiement demandé pour recevoir le lot", 35),
    (r"(iban|rib|coordonnees bancaires|numero de carte|card number|cvv|cryptogramme|code secret|mot de passe|password)", "Demande de données bancaires ou secrètes", 40),
    (r"(western union|moneygram|bitcoin|crypto|carte (prepayee|cadeau)|gift card|pcs|transcash|neosurf|paysafecard)", "Moyen de paiement non traçable", 30),
    (r"(urgent|immediatement|sous 24 ?h|within 24 hours|derniere chance|last chance|expire aujourd|act now)", "Pression temporelle", 15),
    (r"(cher (client|gagnant|utilisateur)|dear (winner|customer|user))", "Formule générique", 10),
    (r"(bit\.ly|tinyurl|t\.co/|goo\.gl|is\.gd|cutt\.ly|rebrand\.ly)", "Lien raccourci", 15),
    (r"(selectionne au hasard|randomly selected).{0,60}(adresse e-?mail|email address)", "« Votre adresse a été sélectionnée »", 15),
    (r"(numero (de telephone )?surtaxe|appelez le 08 9|0899)", "Numéro surtaxé", 25),
]
LINK = re.compile(r"https?://[^\s<>\"')]+", re.I)


def analyze_message(text: str | None, sender: str | None, organizer_domain: str | None, participated: bool) -> tuple[int, list[str]]:
    t = norm(text or "")
    score, flags = 0, []
    for pat, label, pts in RULES:
        if re.search(pat, t):
            score += pts
            flags.append(label)
    if not participated:
        score += 30
        flags.append("Aucune participation enregistrée pour ce concours")
    if sender:
        if FREE_MAIL.search(sender):
            score += 10
            flags.append("Expéditeur sur messagerie gratuite")
        sdom = sender.split("@")[-1].lower().strip("> ")
        if organizer_domain and "@" in sender and not (sdom == organizer_domain or sdom.endswith("." + organizer_domain) or organizer_domain.endswith("." + sdom)):
            score += 15
            flags.append(f"Domaine de l'expéditeur ({sdom}) différent de l'organisateur ({organizer_domain})")
    if organizer_domain:
        for link in LINK.findall(text or ""):
            h = (urlsplit(link).hostname or "").lower().removeprefix("www.")
            if h and not (h == organizer_domain or h.endswith("." + organizer_domain)):
                score += 10
                flags.append(f"Lien vers un autre domaine : {h}")
                break
    return min(100, score), flags
