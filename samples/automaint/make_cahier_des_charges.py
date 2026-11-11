#!/usr/bin/env python3
"""Génère le document de démonstration de l'import : un cahier des charges de maintenance automobile, 2 pages.

- français (défaut) : samples/automaint/automaint-cahier-des-charges.pdf ;
- anglais (``--lang en``) : samples/automaint/automaint-requirements.pdf.

Usage : python samples/automaint/make_cahier_des_charges.py [--lang fr|en] [sortie.pdf]
Utilise reportlab s'il est installé ; sinon écrit un PDF minimal à la main (Helvetica, texte natif, aucune dépendance).
Le texte est volontairement générique : aucune donnée d'entreprise réelle.
"""
from __future__ import annotations

import pathlib
import sys
import textwrap

H, B, P = "heading", "title", "para"
PAGES = [
    [(B, "Cahier des charges : suivi de la maintenance automobile"),
     (P, "Version 1.0 - Application destinée au Garage Martin"),
     (H, "1. Contexte"),
     (P, "Le Garage Martin souhaite suivre l'entretien des véhicules de ses clients. Un Garage reçoit chaque jour plusieurs "
         "Véhicules et réalise des interventions de maintenance. L'application doit remplacer le classeur papier."),
     (H, "2. Définitions"),
     (P, "Véhicule : engin routier confié au garage pour entretien ou réparation."),
     (P, "Garage : atelier qui accueille les véhicules et emploie des mécaniciens."),
     (P, "Pneu : pièce de caoutchouc montée sur une roue du véhicule."),
     (P, "Contrôle technique : inspection réglementaire d'un véhicule."),
     (H, "3. Exigences sur les véhicules"),
     (P, "Un Véhicule a un numéro VIN, une plaque, un kilométrage et une date d'achat. Un Véhicule est équipé de Pneus."),
     (P, "Une Voiture est un Véhicule léger. Une Voiture a une puissance fiscale. Un Camion est un Véhicule lourd.")],
    [(H, "4. Pneus"),
     (P, "Un Pneu est une Pièce. Un Pneu a une référence, une dimension, une pression et une date de fabrication. "
         "Le Garage remplace le Pneu lorsque la profondeur des sculptures est insuffisante."),
     (H, "5. Contrôle technique"),
     (P, "Le Contrôle technique est obligatoire tous les deux ans. Un Contrôle technique concerne un Véhicule."),
     (P, "Un Contrôle technique a une date, un résultat et un centre agréé."),
     (H, "6. Questions de compétence"),
     (P, "Quels véhicules ont un contrôle technique à renouveler ce mois-ci ?"),
     (P, "Quels pneus équipent un véhicule donné ?"),
     (P, "Quelle est la date du dernier contrôle technique d'un véhicule ?"),
     (P, "Quel mécanicien a réalisé chaque intervention ?"),
     (P, "Quelles voitures ont dépassé 100 000 kilomètres ?")],
]


PAGES_EN = [
    [(B, "Requirements specification: car maintenance tracking"),
     (P, "Version 1.0 - Application for Martin Garage"),
     (H, "1. Context"),
     (P, "Martin Garage wants to track the servicing of its customers' vehicles. A Garage receives several "
         "Vehicles every day and carries out maintenance jobs. The application must replace the paper binder."),
     (H, "2. Definitions"),
     (P, "Vehicle: road machine entrusted to the garage for servicing or repair."),
     (P, "Garage: workshop that receives vehicles and employs mechanics."),
     (P, "Tyre: rubber part fitted on a wheel of the vehicle."),
     (P, "Technical inspection: statutory inspection of a vehicle."),
     (H, "3. Requirements on vehicles"),
     (P, "A Vehicle has a VIN number, a plate, a mileage and a purchase date. A Vehicle is fitted with Tyres."),
     (P, "A Sedan is a light Vehicle. A Sedan has a fiscal horsepower. A Truck is a heavy Vehicle.")],
    [(H, "4. Tyres"),
     (P, "A Tyre is a Part. A Tyre has a reference, a size, a pressure and a manufacturing date. "
         "The Garage replaces the Tyre when the tread depth is insufficient."),
     (H, "5. Technical inspection"),
     (P, "The Technical inspection is mandatory every two years. A Technical inspection concerns a Vehicle."),
     (P, "A Technical inspection has a date, a result and an approved centre."),
     (H, "6. Competency questions"),
     (P, "Which vehicles have a technical inspection to renew this month?"),
     (P, "Which tyres are fitted on a given vehicle?"),
     (P, "What is the date of the last technical inspection of a vehicle?"),
     (P, "Which mechanic carried out each job?"),
     (P, "Which sedans exceed 100,000 kilometres?")],
]
PAGES_BY_LANG = {"fr": PAGES, "en": PAGES_EN}
FILENAMES = {"fr": "automaint-cahier-des-charges.pdf", "en": "automaint-requirements.pdf"}


def _esc(s: str) -> bytes:
    return s.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def build_pdf(pages=PAGES) -> bytes:
    """PDF minimal écrit à la main : une police Helvetica / Helvetica-Bold en WinAnsiEncoding, texte natif extractible."""
    objs: list[bytes] = []
    n_pages = len(pages)
    first_page_obj = 4
    streams = []
    for items in pages:
        y = 790
        out = [b"BT"]
        for kind, text in items:
            size, font, gap = (15, "F2", 26) if kind == B else (12, "F2", 22) if kind == H else (11, "F1", 15)
            if kind == H:
                y -= 8
            width = 62 if kind == B else 88
            for ln in textwrap.wrap(text, width):
                out.append(b"/%s %d Tf 1 0 0 1 56 %d Tm (%s) Tj" % (font.encode(), size, y, _esc(ln)))
                y -= gap if kind != P else 15
            if kind == P:
                y -= 5
        out.append(b"ET")
        streams.append(b"\n".join(out))
    kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(n_pages)).encode()
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % n_pages)
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")  # obj 3 = F1
    for i, st in enumerate(streams):
        page_no = first_page_obj + 2 * i
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>"
                    % (first_page_obj + 2 * n_pages, page_no + 1))
        objs.append(b"<< /Length %d >>\nstream\n" % len(st) + st + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")  # F2
    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(buf))
        buf += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(buf)
    buf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        buf += b"%010d 00000 n \n" % off
    buf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(buf)


def build_with_reportlab(pages=PAGES) -> bytes:
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    for items in pages:
        y = 790
        for kind, text in items:
            size, font = (15, "Helvetica-Bold") if kind == B else (12, "Helvetica-Bold") if kind == H else (11, "Helvetica")
            if kind == H:
                y -= 8
            for ln in textwrap.wrap(text, 62 if kind == B else 88):
                c.setFont(font, size)
                c.drawString(56, y, ln)
                y -= 26 if kind == B else 22 if kind == H else 15
            if kind == P:
                y -= 5
        c.showPage()
    c.save()
    return bio.getvalue()


def make(path: pathlib.Path, lang: str = "fr") -> None:
    pages = PAGES_BY_LANG[lang]
    try:
        data = build_with_reportlab(pages)
    except ImportError:
        data = build_pdf(pages)
    path.write_bytes(data)


if __name__ == "__main__":
    args = sys.argv[1:]
    lang = "fr"
    if "--lang" in args:
        k = args.index("--lang")
        lang = args[k + 1] if k + 1 < len(args) else ""
        del args[k:k + 2]
    if lang not in PAGES_BY_LANG:
        sys.exit("--lang doit valoir fr ou en / --lang must be fr or en")
    out = pathlib.Path(args[0]) if args else pathlib.Path(__file__).with_name(FILENAMES[lang])
    make(out, lang)
    print(out, out.stat().st_size, "octets")
