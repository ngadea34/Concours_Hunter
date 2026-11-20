from datetime import date, timedelta

RULES = """Règlement du jeu « {title} »
Article 1 – Organisateur : la société Exemple Jouets SAS, immatriculée au RCS de Lyon sous le numéro 512 345 678, organise un jeu gratuit et sans obligation d'achat.
Article 2 – Participation : le jeu est ouvert à toute personne physique majeure résidant en France métropolitaine.
Le jeu se déroule du {start:%d/%m/%Y} au {end:%d/%m/%Y} à 23h59.
Une seule participation par personne (même nom, même adresse).
Article 3 – Dotation : une console PlayStation 5 d'une valeur de 549 €.
Article 4 – Le tirage au sort aura lieu le {draw:%d/%m/%Y}. Les gagnants seront informés par e-mail le {pub:%d/%m/%Y}.
"""


def qualified(db, title="Gagnez une PS5", end=None, url=None, draw=None, pub=None, **attrs):
    from conftest import make_contest

    today = date.today()
    end = end or today + timedelta(days=10)
    draw = draw or end + timedelta(days=3)
    pub = pub or draw + timedelta(days=2)
    url = url or f"https://jouets-exemple.test/{abs(hash(title)) % 10**8}"
    c = make_contest(db, title=title, url=url, rules_text=RULES.format(title=title, start=today - timedelta(days=5), end=end, draw=draw, pub=pub))
    for k, v in attrs.items():
        setattr(c, k, v)
    db.commit()
    return c
