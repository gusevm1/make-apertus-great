from app.features.boards.subscriptions import subscription_payees

PAYMENTS = [
    {"type": "standing_order", "payee_name": "Wohnbau Sihlfeld AG", "description": "Miete Dezember 2026"},
    {"type": "direct_debit", "payee_name": "Fitnesspark Zürich", "description": "Mitgliedschaft Dezember 2026"},
    {"type": "direct_debit", "payee_name": "Salt Mobile SA", "description": "Abo Mobile Dezember 2026"},
    {"type": "ebill", "payee_name": "Swisscom (Schweiz) AG", "description": "Rechnung inOne home Dezember 2026"},
    {"type": "ebill", "payee_name": "Mythen Krankenversicherung AG", "description": "Prämie Januar 2027"},
    {"type": "direct_debit", "payee_name": "Ratenwerk Finanz AG", "description": "Ratenvertrag, Rate 21/24"},
    {"type": "direct_debit", "payee_name": "Salt Mobile SA", "description": "Abo Mobile Januar 2027"},
]


def test_subscriptions_come_from_the_bank_text() -> None:
    assert subscription_payees(payments=PAYMENTS) == [
        "Fitnesspark Zürich",
        "Salt Mobile SA",
        "Swisscom (Schweiz) AG",
    ]
