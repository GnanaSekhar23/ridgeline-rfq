"""Build tests/synthetic/emails/*.eml — made-up situations the dev inbox does not show.

Run once; the .eml files are committed (Office files embed timestamps, so rebuilding would
change their bytes and therefore the cache keys). All names, companies and parts are invented.

    python tests/synthetic/build_synthetic.py
"""

from __future__ import annotations

from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import docx
import openpyxl
from openpyxl.styles import Font
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "emails"
RFQ = "Ridgeline RFQ Desk <rfq@ridgeline-supply.example>"


def msg(sid: str, frm: str, subject: str, date: str, body: str, *, irt: str | None = None,
        extra: dict | None = None) -> EmailMessage:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Date"] = frm, RFQ, subject, date
    m["Message-ID"] = f"<{sid.lower()}.synthetic@{frm.split('@')[1].rstrip('>')}>"
    if irt:
        m["In-Reply-To"] = m["References"] = irt
    for k, v in (extra or {}).items():
        m[k] = v
    m.set_content(body)
    return m


def xlsx_with_struck_row() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Valves"
    ws.append(["Item", "Qty", "UOM", "Size", "Description"])
    ws.append([1, 8, "EA", '1"', "Ball valve, 2-pc, 316 SS, threaded, 1000 WOG"])
    ws.append([2, 4, "EA", '1-1/2"', "Ball valve, 2-pc, 316 SS, threaded, 1000 WOG"])
    ws.append([3, 6, "EA", '1"', "Union, 316 SS, threaded, 3000#"])
    ws.append([4, 2, "EA", '2"', "Y-strainer, 316 SS, threaded, 800#"])
    for c in ws[4]:
        c.font = Font(strike=True)  # item 3 (unions) crossed out
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def list_photo_png() -> bytes:
    """A 'phone photo' of a typed list on lined paper (slightly rotated)."""
    img = Image.new("RGB", (900, 620), (247, 244, 236))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=34)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    for y in range(90, 620, 70):
        d.line([(40, y + 38), (860, y + 38)], fill=(170, 190, 220), width=2)
    lines = ["Shop list - boiler room", '6 - 3/4" ball valve, brass, threaded',
             '10 - 3/4" 90 ell, black MI 150#', '4 - 3/4" x 6" nipple, black sch 40',
             '2 - 3/4" union, black MI 150#']
    for i, t in enumerate(lines):
        d.text((60, 90 + i * 70), t, fill=(30, 30, 60), font=font)
    img = img.rotate(2.5, expand=True, fillcolor=(90, 90, 90))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def docx_with_photo() -> bytes:
    d = docx.Document()
    d.add_paragraph("Material request - see the photo of the list from the field.")
    d.add_picture(BytesIO(list_photo_png()), width=docx.shared.Inches(5.5))
    d.add_paragraph("Deliver to the north gate.")
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def build() -> list[tuple[str, EmailMessage]]:
    out = []

    out.append(("S01", msg(
        "S01", "Carla Benoit <cbenoit@marshlandfab.example>",
        "Automatic reply: RFQ MF-1182 stainless fittings", "Mon, 09 Nov 2026 07:02:00 -0600",
        "Thank you for your email. I am out of the office until Monday, November 16 with limited "
        "access to email.\n\nFor urgent purchasing matters please contact Dean Hollis at "
        "dhollis@marshlandfab.example or 337-555-0144.\n\nCarla Benoit\nMarshland Fabrication",
        extra={"Auto-Submitted": "auto-replied", "X-Autoreply": "yes"})))

    out.append(("S02", msg(
        "S02", "Ray Thibault <ray@bayoumech.example>", "pricing - repeat order",
        "Mon, 09 Nov 2026 09:15:00 -0600",
        "Hi,\n\nCan you price the same as our last order, but double it? Need it for the second "
        "unit at the plant.\n\nThanks\nRay\nBayou Mechanical")))

    out.append(("S03", msg(
        "S03", "Lena Ortiz <lortiz@gulfpointenergy.example>", "Re: RFQ GP-7731 valve package",
        "Mon, 09 Nov 2026 11:40:00 -0600",
        "Two changes please:\n\nItem 2 - make it 6 instead of 4.\nAnd add 2 ea 4\" 150# swing check "
        "valve, flanged, WCB.\n\nEverything else the same.\n\nLena\n\n"
        "On Thu, Nov 5, 2026 at 2:10 PM Lena Ortiz <lortiz@gulfpointenergy.example> wrote:\n"
        "> Please quote:\n>\n> 1) 10 ea 2\" 150# RF weld neck flange, A105\n"
        "> 2) 4 ea 4\" 150# gate valve, flanged, WCB\n> 3) 20 ea 2\" 150# spiral wound gasket, 304/graphite\n"
        ">\n> Thanks,\n> Lena Ortiz\n> Gulf Point Energy\n",
        irt="<gp7731.original@gulfpointenergy.example>")))

    m = msg("S04", "Owen Price <oprice@cyprusprocess.example>", "RFQ CP-2209 - SS valves",
            "Mon, 09 Nov 2026 13:05:00 -0600",
            "Hello,\n\nPlease quote the attached list. We crossed out the unions, we have those.\n\n"
            "Owen Price\nCypress Process Services")
    m.add_attachment(xlsx_with_struck_row(), maintype="application",
                     subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="CP-2209_valves.xlsx")
    out.append(("S04", m))

    m = msg("S05", "Gus Merrick <gus@redstickboiler.example>", "boiler room material",
            "Mon, 09 Nov 2026 14:20:00 -0600",
            "Need pricing on the list in the attached doc please.\n\nGus")
    m.add_attachment(docx_with_photo(), maintype="application",
                     subtype="vnd.openxmlformats-officedocument.wordprocessingml.document", filename="boiler_room_list.docx")
    out.append(("S05", m))

    out.append(("S06", msg(
        "S06", "Accounts Payable <ap@lakeshorepetro.example>", "Remittance advice - payment 0098812",
        "Tue, 10 Nov 2026 08:00:00 -0600",
        "Remittance advice\n\nPayment number: 0098812\nPayment date: 11/10/2026\nAmount: $4,512.30 USD\n\n"
        "Invoices paid:\nINV-552019   $3,120.00\nINV-552044   $1,392.30\n\n"
        "This payment was sent by ACH to the account on file.\nLakeshore Petrochemical - Accounts Payable")))

    out.append(("S07", msg(
        "S07", "Nadia Fontenot <nfontenot@crescentmech.example>", "Re: Quote Q-26-05093",
        "Tue, 10 Nov 2026 10:30:00 -0600",
        "Hi,\n\nThanks for turning the quote around so fast. We've decided to go with another "
        "supplier on this one - they had the 6\" valves in stock locally.\n\nWe'll keep you in "
        "mind for the next job.\n\nNadia",
        irt="<q2605093@ridgeline-supply.example>")))

    out.append(("S08", msg(
        "S08", "Tim Arceneaux <tarceneaux@pelicanplant.example>", "PO 77812",
        "Tue, 10 Nov 2026 12:45:00 -0600",
        "Please accept this email as our PO 77812 against your quote Q-26-05120. Ship to our "
        "Sulphur yard, freight prepaid and add.\n\nTim Arceneaux\nPelican Plant Services")))

    out.append(("S09", msg(
        "S09", "Jo Landreneau <jo@acadianaweld.example>", "quick quote",
        "Tue, 10 Nov 2026 15:10:00 -0600",
        "Hey, need a price on twelve 2\" 90 deg elbows, sch 40 butt weld, six 2\" tees same, "
        "and a couple of 2\" caps.\n\nThanks, Jo")))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sid, m in build():
        (OUT / f"{sid}.eml").write_bytes(m.as_bytes())
        print("wrote", sid)


if __name__ == "__main__":
    main()
