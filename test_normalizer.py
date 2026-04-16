from payee_normalizer import normalize_payee

examples = [
    "ZETTLE_*CHILDREN S TOY",
    "SUMUP *WAFFLE STATION LI",
    "SQ *BURGER BUZZ",
    "Payment to SURREY FLOORS & DO 2024-02-09",
    "348855063THE PIRB",
    "Non-Sterling transaction fee 2024-10-06",
    "ATM Withdrawal SAINSBURYS BANK 2024-04-15",
    "WWW.MINERVACRAFTS.COM",
    "AMZNMktplace",
]

for e in examples:
    print(f"{e!r} -> {normalize_payee(e)!r}")