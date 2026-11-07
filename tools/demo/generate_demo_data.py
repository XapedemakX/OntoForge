"""Génère samples/automaint/automaint-demo-data.ttl (données fictives réalistes, reproductibles).

Usage : python tools/demo/generate_demo_data.py [sortie.ttl]   (graine fixe : même fichier à chaque exécution)
Conforme à samples/automaint/automaint-shapes.ttl (validation SANS inférence : les types sont posés explicitement,
y compris les super-classes visées par les shapes : Vehicle, Engine).
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace

SEED = 20261105
AM = Namespace("https://w3id.org/ontoforge/automaint#")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "samples" / "automaint" / "automaint-demo-data.ttl"
DATE_MIN, DATE_MAX = datetime(2025, 1, 6, 8, 0), datetime(2026, 10, 30, 17, 0)
OPEN_AFTER = datetime(2026, 10, 20)  # ordres ouverts après cette date : pas encore clos

# (clé, marque, modèle, année, genre, cylindrée cc, puissance kW)
MODELS = [
    ("clio", "Renault", "Clio V", 2021, "petrol", 999, 67),
    ("megane_e", "Renault", "Mégane E-Tech", 2023, "ev", None, 160),
    ("p308", "Peugeot", "308", 2022, "diesel", 1499, 96),
    ("e208", "Peugeot", "e-208", 2022, "ev", None, 100),
    ("c3", "Citroën", "C3", 2020, "petrol", 1199, 61),
    ("duster", "Dacia", "Duster", 2022, "diesel", 1461, 85),
    ("yaris_h", "Toyota", "Yaris Hybride", 2023, "hybrid", 1490, 68),
    ("ioniq_h", "Hyundai", "Ioniq Hybride", 2021, "hybrid", 1580, 77),
]
SUPPLIERS = ["Bosch", "Valeo", "Brembo", "Mann-Filter", "Michelin", "Varta", "NGK", "Denso"]
GARAGES = [("toulouse", "Garage du Capitole — Toulouse"), ("lyon", "Atelier Confluence — Lyon"),
           ("bordeaux", "Garage des Chartrons — Bordeaux"), ("nantes", "Auto Service Île de Nantes — Nantes"),
           ("lille", "Garage Vieux-Lille — Lille"), ("marseille", "Mécanique du Vieux-Port — Marseille")]
FIRST = ["Camille", "Alex", "Sacha", "Claude", "Dominique", "Morgan", "Charlie", "Andrea", "Louison", "Maxime",
         "Lou", "Noa", "Eden", "Yael", "Robin", "Sam", "Jules", "Marion", "Lena", "Hugo", "Théo", "Inès",
         "Nina", "Léo", "Eloi", "Mila", "Gaël", "Ivan", "Anaïs", "Romane", "Tom", "Zoé", "Basile", "Océane", "Elio",
         "Maëlle", "Axel", "Jade", "Loïc", "Faustine", "Nolan", "Clémence", "Rémi", "Salomé", "Victor"]
LAST = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau",
        "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
        "Morel", "Girard", "André", "Mercier", "Dupont", "Lambert", "Bonnet", "François", "Martinez", "Legrand",
        "Garnier", "Faure", "Rousseau", "Blanc", "Guerin", "Muller", "Henry", "Roussel", "Nicolas", "Perrin",
        "Morin", "Mathieu", "Clément", "Gauthier", "Dumont"]

# Codes défaut OBD-II : (code, libellé fr)
DTCS = [("P0300", "Ratés d'allumage détectés (multi-cylindres)"), ("P0301", "Raté d'allumage cylindre 1"),
        ("P0420", "Efficacité du catalyseur sous le seuil (rangée 1)"), ("P0171", "Mélange trop pauvre (rangée 1)"),
        ("P0101", "Débitmètre d'air : plage / performance"), ("P0401", "Débit de recirculation des gaz (EGR) insuffisant"),
        ("P2002", "Efficacité du filtre à particules sous le seuil"), ("P0299", "Suralimentation insuffisante (turbo)"),
        ("P0A80", "Remplacer le pack de batterie hybride"), ("P0AA6", "Défaut d'isolement du circuit haute tension"),
        ("C0035", "Capteur de vitesse de roue avant gauche : circuit"), ("U0100", "Communication perdue avec le calculateur moteur")]

# Références de pièces : (clé, libellé fr, fournisseur, référence fabricant, prix)
PARTS = [
    ("filtre_huile", "Filtre à huile", "Mann-Filter", "MF-HU712", "12.90"), ("huile", "Huile moteur 5W-30 (5 L)", "Bosch", "BS-OIL-5W30-5", "49.50"),
    ("filtre_air", "Filtre à air", "Mann-Filter", "MF-C25114", "18.40"), ("filtre_hab", "Filtre d'habitacle", "Valeo", "VL-715631", "21.00"),
    ("plaq_av", "Jeu de plaquettes avant", "Brembo", "BR-P85020", "64.80"), ("disque_av", "Paire de disques avant", "Brembo", "BR-09A7", "119.00"),
    ("pneu", "Pneu 195/55 R16 (unité)", "Michelin", "MI-195-55-16", "89.90"), ("batt12", "Batterie 12 V 60 Ah", "Varta", "VA-E11", "129.00"),
    ("bougie", "Bougie d'allumage", "NGK", "NG-ZFR6", "11.20"), ("bobine", "Bobine d'allumage", "Bosch", "BS-0221504", "47.50"),
    ("catalyseur", "Catalyseur", "Denso", "DN-CAT-4421", "389.00"), ("fap", "Filtre à particules", "Denso", "DN-FAP-7730", "540.00"),
    ("egr", "Vanne EGR", "Valeo", "VL-700421", "215.00"), ("debitmetre", "Débitmètre d'air", "Bosch", "BS-0280218", "98.00"),
    ("courroie", "Courroie d'accessoires", "Valeo", "VL-CA-6PK", "34.00"), ("capteur_abs", "Capteur de vitesse de roue", "Bosch", "BS-0986594", "42.60"),
    ("liq_frein", "Liquide de frein DOT 4 (1 L)", "Bosch", "BS-DOT4-1", "13.50"), ("pompe_refroid", "Pompe de refroidissement batterie", "Valeo", "VL-PRB-300", "310.00"),
    ("turbo", "Turbocompresseur", "Denso", "DN-TURBO-18", "690.00"), ("cellule_hv", "Module de batterie haute tension", "Denso", "DN-HV-M24", "1450.00"),
]

KINDS = {"petrol", "diesel", "hybrid", "ev"}
THERMAL = {"petrol", "diesel", "hybrid"}
# Opérations : (clé, code, libellé fr, durée min, pièces, genres admis, codes défaut traités)
OPS = [
    ("vidange", "OP-VIDANGE", "Vidange moteur et remplacement du filtre à huile", 45, ["filtre_huile", "huile"], THERMAL, []),
    ("f_air", "OP-FILTRE-AIR", "Remplacement du filtre à air", 20, ["filtre_air"], THERMAL, []),
    ("f_hab", "OP-FILTRE-HABITACLE", "Remplacement du filtre d'habitacle", 15, ["filtre_hab"], KINDS, []),
    ("plaq", "OP-PLAQUETTES-AV", "Remplacement des plaquettes de frein avant", 60, ["plaq_av"], KINDS, []),
    ("disque", "OP-DISQUES-AV", "Remplacement des disques et plaquettes avant", 95, ["disque_av", "plaq_av"], KINDS, []),
    ("pneus", "OP-PNEUS", "Remplacement de deux pneus et équilibrage", 50, ["pneu"], KINDS, []),
    ("batt", "OP-BATTERIE-12V", "Remplacement de la batterie 12 V", 30, ["batt12"], KINDS, []),
    ("liq", "OP-LIQUIDE-FREIN", "Purge et remplacement du liquide de frein", 40, ["liq_frein"], KINDS, []),
    ("bougies", "OP-BOUGIES", "Remplacement des bougies d'allumage", 60, ["bougie"], {"petrol", "hybrid"}, ["P0300"]),
    ("bobine", "OP-BOBINE", "Remplacement d'une bobine d'allumage", 40, ["bobine"], {"petrol", "hybrid"}, ["P0301", "P0300"]),
    ("cata", "OP-CATALYSEUR", "Remplacement du catalyseur", 120, ["catalyseur"], {"petrol", "hybrid"}, ["P0420"]),
    ("debit", "OP-DEBITMETRE", "Remplacement du débitmètre d'air", 35, ["debitmetre"], {"petrol", "diesel"}, ["P0101", "P0171"]),
    ("fap", "OP-FAP", "Remplacement du filtre à particules", 150, ["fap"], {"diesel"}, ["P2002"]),
    ("egr", "OP-EGR", "Remplacement de la vanne EGR", 100, ["egr"], {"diesel"}, ["P0401"]),
    ("turbo", "OP-TURBO", "Remplacement du turbocompresseur", 210, ["turbo"], {"diesel"}, ["P0299"]),
    ("courroie", "OP-COURROIE-ACC", "Remplacement de la courroie d'accessoires", 60, ["courroie"], THERMAL, []),
    ("abs", "OP-CAPTEUR-ABS", "Remplacement d'un capteur de vitesse de roue", 45, ["capteur_abs"], KINDS, ["C0035"]),
    ("refroid", "OP-REFROID-BATTERIE", "Remplacement de la pompe de refroidissement de batterie", 90, ["pompe_refroid"], {"ev", "hybrid"}, ["P0AA6"]),
    ("hv", "OP-MODULE-HV", "Remplacement d'un module de batterie haute tension", 240, ["cellule_hv"], {"ev", "hybrid"}, ["P0A80"]),
    ("diag", "OP-DIAGNOSTIC", "Diagnostic électronique (lecture des codes défaut)", 30, [], KINDS, ["U0100"]),
]
RECALLS = [  # (numéro, émission, modèles, pièce concernée)
    ("RC-2025-014", datetime(2025, 4, 14), ["clio", "c3"], "bobine"),
    ("RC-2025-031", datetime(2025, 9, 2), ["duster", "p308"], "egr"),
    ("RC-2026-007", datetime(2026, 3, 9), ["megane_e", "e208"], "pompe_refroid"),
]


def dt(d: datetime) -> Literal:
    return Literal(d.strftime("%Y-%m-%dT%H:%M:%S"), datatype=XSD.dateTime)


def build(seed: int = SEED) -> Graph:
    rnd = random.Random(seed)
    g = Graph()
    g.bind("am", AM)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    def fr(node, text):
        g.add((node, RDFS.label, Literal(text, lang="fr")))

    # --- marques, modèles
    brands: dict[str, object] = {}

    def brand(name):
        if name not in brands:
            b = AM["brand_" + name.lower().replace("é", "e").replace("ë", "e").replace("ï", "i").replace("-", "_")]
            g.add((b, RDF.type, AM.Brand))
            g.add((b, AM.brandName, Literal(name)))
            g.add((b, AM.displayName, Literal(name)))
            fr(b, name)
            brands[name] = b
        return brands[name]

    models = {}
    for key, bname, mname, year, kind, cc, kw in MODELS:
        m = AM["model_" + key]
        g.add((m, RDF.type, AM.VehicleModel))
        g.add((m, AM.modelName, Literal(mname)))
        g.add((m, AM.modelYear, Literal(year, datatype=XSD.integer)))
        g.add((m, AM.madeBy, brand(bname)))
        fr(m, f"{bname} {mname}")
        models[key] = (m, kind, cc, kw)
    for s in SUPPLIERS:
        brand(s)

    # --- pièces (références), opérations, codes défaut
    refs = {}
    for key, label, sup, mpn, price in PARTS:
        r = AM["ref_" + key]
        g.add((r, RDF.type, AM.PartReference))
        g.add((r, AM.manufacturerPartNumber, Literal(mpn)))
        g.add((r, AM.hasManufacturer, brand(sup)))
        g.add((r, AM.unitPrice, Literal(price, datatype=XSD.decimal)))
        fr(r, label)
        refs[key] = r
    dtcs = {}
    for code, label in DTCS:
        d = AM["dtc_" + code]
        g.add((d, RDF.type, AM.DiagnosticTroubleCode))
        g.add((d, AM.dtcCode, Literal(code)))
        fr(d, f"{code} — {label}")
        dtcs[code] = d
    ops = {}
    for key, code, label, dur, parts, kinds, codes in OPS:
        o = AM["op_" + key]
        g.add((o, RDF.type, AM.ServiceOperation))
        g.add((o, AM.operationCode, Literal(code)))
        g.add((o, AM.standardDurationMin, Literal(dur, datatype=XSD.integer)))
        fr(o, label)
        for p in parts:
            g.add((o, AM.usesPart, refs[p]))
        for c in codes:
            g.add((o, AM.addresses, dtcs[c]))
        ops[key] = (o, parts, kinds, codes)

    # --- plans d'entretien (un par modèle)
    for key, (m, kind, _, _) in models.items():
        pl = AM["plan_" + key]
        g.add((pl, RDF.type, AM.MaintenancePlan))
        g.add((pl, AM.plannedFor, m))
        g.add((pl, AM.intervalKm, Literal(30000 if kind == "ev" else 15000, datatype=XSD.integer)))
        g.add((pl, AM.intervalMonths, Literal(24 if kind == "ev" else 12, datatype=XSD.integer)))
        g.add((pl, AM.prescribes, ops["f_hab" if kind == "ev" else "vidange"][0]))
        fr(pl, "Plan d'entretien " + str(g.value(m, AM.modelName)))

    # --- garages, techniciens, clients (noms inventés, génériques)
    names = [f"{f} {l}" for f in FIRST for l in LAST]
    rnd.shuffle(names)
    garages = {}
    for key, name in GARAGES:
        ga = AM["garage_" + key]
        g.add((ga, RDF.type, AM.Garage))
        g.add((ga, AM.displayName, Literal(name)))
        fr(ga, name)
        garages[key] = ga
    gkeys = list(garages)
    techs: dict[str, list] = {k: [] for k in gkeys}
    for i in range(15):
        k = gkeys[i % 6] if i < 6 else rnd.choice(gkeys)
        t = AM[f"tech_{i + 1:02d}"]
        n = names.pop()
        g.add((t, RDF.type, AM.Technician))
        g.add((t, AM.displayName, Literal(n)))
        g.add((t, AM.worksAt, garages[k]))
        fr(t, n)
        techs[k].append(t)
    customers = []
    for i in range(30):
        c = AM[f"client_{i + 1:02d}"]
        n = names.pop()
        g.add((c, RDF.type, AM.Customer))
        g.add((c, AM.displayName, Literal(n)))
        fr(c, n)
        customers.append((c, rnd.choice(gkeys)))

    # --- véhicules
    kinds_mix = [m for m in models for _ in range(5)]  # 8 modèles x 5 = 40
    rnd.shuffle(kinds_mix)
    alphabet = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    vins, plates, vehicles = set(), set(), []
    for i, mk in enumerate(kinds_mix):
        m, kind, cc, kw = models[mk]
        year = int(g.value(m, AM.modelYear))
        while True:
            vin = "VF" + rnd.choice("123457") + "".join(rnd.choice(alphabet) for _ in range(14))
            if vin not in vins:
                vins.add(vin)
                break
        while True:
            plate = "".join(rnd.choice("ABCDEFGHJKLMNPQRSTVWXYZ") for _ in range(2)) + "-%03d-" % rnd.randint(1, 999) \
                + "".join(rnd.choice("ABCDEFGHJKLMNPQRSTVWXYZ") for _ in range(2))
            if plate not in plates:
                plates.add(plate)
                break
        v = AM[f"veh_{i + 1:02d}"]
        cust, home = customers[i % 30] if i < 30 else rnd.choice(customers)
        first_reg = datetime(year, 1, 15) + timedelta(days=rnd.randint(0, 330))
        g.add((v, RDF.type, AM.Vehicle))
        g.add((v, AM.vin, Literal(vin)))
        g.add((v, AM.registrationNumber, Literal(plate)))
        g.add((v, AM.ofModel, m))
        g.add((v, AM.firstRegistrationDate, dt(first_reg.replace(hour=0))))
        g.add((v, AM.ownedBy, cust))
        fr(v, f"{g.value(m, RDFS.label)} {plate}")
        g.add((v, RDF.type, AM.CombustionVehicle if kind in ("petrol", "diesel") else AM.ElectricVehicle if kind == "ev" else AM.Vehicle))
        # moteurs (une hybride a un moteur thermique ET un moteur électrique ; aucun type disjoint posé)
        engines = []
        if kind != "ev":
            engines.append(("ice", AM.InternalCombustionEngine, cc, kw, AM.Diesel if kind == "diesel" else AM.Petrol))
        if kind in ("ev", "hybrid"):
            engines.append(("elec", AM.ElectricMotor, None, kw if kind == "ev" else 43, AM.Electric))
        for tag, cls, ccv, kwv, fuel in engines:
            e = AM[f"eng_{i + 1:02d}_{tag}"]
            g.add((e, RDF.type, AM.Engine))
            g.add((e, RDF.type, cls))
            if ccv:
                g.add((e, AM.displacementCc, Literal(ccv, datatype=XSD.integer)))
            g.add((e, AM.powerKw, Literal(kwv, datatype=XSD.decimal)))
            g.add((e, AM.usesFuel, fuel))
            fr(e, ("Moteur électrique " if tag == "elec" else "Moteur thermique ") + str(g.value(m, AM.modelName)))
            g.add((v, AM.hasEngine, e))
        # garantie
        if rnd.random() < 0.7:
            w = AM[f"warranty_{i + 1:02d}"]
            months = rnd.choice([24, 36, 60])
            g.add((w, RDF.type, AM.Warranty))
            g.add((w, AM.covers, v))
            g.add((w, AM.warrantyDurationMonths, Literal(months, datatype=XSD.integer)))
            if rnd.random() < 0.8:
                g.add((w, AM.warrantyMaxKm, Literal(rnd.choice([60000, 100000, 150000]), datatype=XSD.integer)))
            fr(w, f"Garantie constructeur {months} mois")
        vehicles.append(dict(iri=v, key=mk, kind=kind, home=home, first_reg=first_reg,
                             rate=rnd.randint(7000, 22000), km0=None, active=[]))

    # --- ordres de réparation : ~3 par véhicule, dates triées, kilométrage croissant
    counts = [3] * 40
    for _ in range(12):
        a, b = rnd.sample(range(40), 2)
        if counts[a] > 1:
            counts[a] -= 1
            counts[b] += 1
    span = (DATE_MAX - DATE_MIN).total_seconds()
    events = []
    for vi, n in enumerate(counts):
        for _ in range(n):
            events.append((DATE_MIN + timedelta(seconds=rnd.random() * span), vi))
    events.sort()
    last_km: dict[int, int] = {}
    for vi, vh in enumerate(vehicles):
        age_days = max(1, (DATE_MIN - vh["first_reg"]).days)
        km = int(age_days / 365 * vh["rate"] + rnd.randint(0, 3000))
        vh["km0"] = km
        r = AM[f"km_{vi + 1:02d}_000"]
        g.add((r, RDF.type, AM.MileageReading))
        g.add((r, AM.readingOf, vh["iri"]))
        g.add((vh["iri"], AM.hasMileageReading, r))
        g.add((r, AM.readingDate, dt(DATE_MIN.replace(hour=0, minute=0))))
        g.add((r, AM.readingMileageKm, Literal(km, datatype=XSD.decimal)))
        last_km[vi] = km
    last_date = {vi: DATE_MIN for vi in range(40)}
    seq = {vi: 0 for vi in range(40)}
    part_n = 0
    for n, (when, vi) in enumerate(events, 1):
        vh = vehicles[vi]
        kind = vh["kind"]
        when = when.replace(microsecond=0, second=0, minute=rnd.choice([0, 15, 30, 45]))
        ro = AM[f"ro_{n:03d}"]
        gk = vh["home"] if rnd.random() < 0.8 else rnd.choice(gkeys)
        tech_pool = techs[gk] or techs[vh["home"]] or [t for l in techs.values() for t in l]
        if not techs[gk]:
            gk = next(k for k in gkeys if techs[k])
            tech_pool = techs[gk]
        v = vh["iri"]
        g.add((ro, RDF.type, AM.RepairOrder))
        g.add((ro, AM.orderNumber, Literal(f"OR-{when.year}-{n:04d}")))
        g.add((ro, AM.openedAt, dt(when)))
        g.add((ro, AM.concerns, v))
        g.add((v, AM.hasRepairOrder, ro))
        g.add((ro, AM.performedAt, garages[gk]))
        g.add((ro, AM.assignedTo, rnd.choice(tech_pool)))
        # opérations adaptées à la motorisation ; 1 à 3, avec souvent un correctif lié à un code défaut
        allowed = [k for k, (_, _, kinds, _) in ops.items() if kind in kinds]
        chosen = []
        if rnd.random() < 0.45:
            fix = [k for k in allowed if ops[k][3] and k != "diag"]
            if fix:
                k = rnd.choice(fix)
                chosen += ["diag", k]
        if not chosen:
            chosen = rnd.sample([k for k in allowed if k != "diag"], rnd.randint(1, 2))
        recalled = [(rc[3]) for rc in RECALLS if vh["key"] in rc[2]]
        for k in chosen:
            g.add((ro, AM.includesOperation, ops[k][0]))
            for pk in ops[k][1]:
                part_n += 1
                p = AM[f"part_{part_n:03d}"]
                g.add((p, RDF.type, AM.Part))
                g.add((p, AM.instanceOf, refs[pk]))
                g.add((p, AM.installedIn, v))
                fr(p, str(g.value(refs[pk], RDFS.label)) + f" (lot {part_n:03d})")
            if ops[k][3] and k != "diag":
                vh["active"].append((when, ops[k][3][0]))
        # kilométrage cohérent : strictement croissant dans le temps pour chaque véhicule
        days = (when - last_date[vi]).total_seconds() / 86400
        km = last_km[vi] + max(1, int(days / 365 * vh["rate"] * rnd.uniform(0.85, 1.15)))
        last_km[vi], last_date[vi] = km, when
        seq[vi] += 1
        r = AM[f"km_{vi + 1:02d}_{seq[vi]:03d}"]
        g.add((r, RDF.type, AM.MileageReading))
        g.add((r, AM.readingOf, v))
        g.add((v, AM.hasMileageReading, r))
        g.add((r, AM.readingDate, dt(when)))
        g.add((r, AM.readingMileageKm, Literal(km, datatype=XSD.decimal)))
        # clôture
        if when < OPEN_AFTER:
            g.add((ro, AM.closedAt, dt(when + timedelta(hours=rnd.choice([3, 5, 8, 26, 30, 50])))))
        fr(ro, f"Ordre {when.year}-{n:04d} — {g.value(v, RDFS.label)}")

    # --- codes défaut actifs : un véhicule sur trois porte un code non résolu (distinct des ordres passés)
    for vi in rnd.sample(range(40), 14):
        vh = vehicles[vi]
        pool = [c for c, _ in DTCS if (vh["kind"] in THERMAL or c[0] != "P" or c in ("P0A80", "P0AA6", "U0100"))]
        pool = [c for c in pool if not (vh["kind"] == "ev" and c in ("P0300", "P0301", "P0420", "P0171", "P0101", "P0401", "P2002", "P0299"))]
        pool = [c for c in pool if not (vh["kind"] != "diesel" and c in ("P0401", "P2002", "P0299"))]
        for c in rnd.sample(pool, rnd.randint(1, 2)):
            g.add((vh["iri"], AM.hasActiveCode, dtcs[c]))

    # --- rappels constructeur
    for num, issued, mkeys, pk in RECALLS:
        rc = AM["recall_" + num.lower().replace("-", "_")]
        g.add((rc, RDF.type, AM.Recall))
        g.add((rc, AM.recallNumber, Literal(num)))
        g.add((rc, AM.issuedAt, dt(issued)))
        g.add((rc, AM.concernsPart, refs[pk]))
        for mk in mkeys:
            g.add((rc, AM.appliesToModel, models[mk][0]))
        fr(rc, f"Rappel {num} — {g.value(refs[pk], RDFS.label)}")
    return g


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    g = build()
    header = ("# OntoForge — jeu de données de DÉMO AutoMaint (fictif, reproductible, graine %d).\n"
              "# Généré par tools/demo/generate_demo_data.py — ne pas éditer à la main. Conforme à automaint-shapes.ttl (0 violation, sans inférence).\n"
              "# Ville des garages : l'ontologie n'a pas de propriété « ville » ; elle figure dans am:displayName (« … — Toulouse »).\n" % SEED)
    out.write_text(header + g.serialize(format="turtle"), encoding="utf-8")
    print(f"{out} : {len(g)} triplets")


if __name__ == "__main__":
    main(sys.argv)
