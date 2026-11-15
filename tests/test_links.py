"""Duplicate and thread-link tests on synthetic emails (no dev data)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image

from rfq.dedupe import find_duplicates
from rfq.models import Attachment, Email
from rfq.pipeline import process_inbox
from rfq.threads import find_parents, norm_subject

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
PDF = Attachment("rfq.pdf", "application/pdf", b"%PDF-1.4 same bytes")


def _png(w: int, h: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def mk(eid: str, body: str, *, hours: int = 0, sender: str = "buyer@cust.example",
       subject: str = "RFQ 100", atts=None, mid: str | None = None,
       irt: str | None = None, refs: str | None = None) -> Email:
    return Email(
        id=eid, body=body, attachments=list(atts or []), sender=sender,
        internal=sender.endswith("@ridgeline-supply.example"),
        date=T0 + timedelta(hours=hours),
        headers={"subject": subject, "message_id": mid or f"<{eid}@x>", "in_reply_to": irt, "references": refs},
    )


ITEMS = "Please quote:\n- 4 ea 2in gate valve\n- 6 ea 3in tee\n"

# ---------------------------------------------------------------- duplicates


def test_resend_with_same_attachment_and_items_is_duplicate() -> None:
    a = mk("A", "RFQ attached.\n" + ITEMS + "Thanks, Sam", atts=[PDF])
    b = mk("B", "Resending in case it got lost.\n" + ITEMS + "Regards", hours=20, atts=[PDF],
           subject="RESEND: RFQ 100")
    assert find_duplicates([b, a]) == {"B": "A"}  # later Date: is the duplicate, whatever the order


def test_same_attachment_but_changed_items_is_not_duplicate() -> None:
    a = mk("A", "RFQ attached.\n" + ITEMS, atts=[PDF])
    b = mk("B", "Same RFQ but also add:\n- 10 ea 4in cap\n- 2 ea 6in union\n", hours=3, atts=[PDF])
    assert find_duplicates([a, b]) == {}


def test_body_only_duplicate_and_different_sender_domain() -> None:
    a = mk("A", ITEMS)
    b = mk("B", ITEMS + "\nsent again", hours=5)
    c = mk("C", ITEMS, hours=6, sender="other@elsewhere.example")
    assert find_duplicates([a, b, c]) == {"B": "A"}


def test_different_attachments_not_duplicate() -> None:
    a = mk("A", "see attached", atts=[PDF])
    b = mk("B", "see attached", hours=1, atts=[Attachment("rfq2.pdf", "application/pdf", b"%PDF other")])
    assert find_duplicates([a, b]) == {}


def test_shared_logo_and_short_body_is_not_duplicate() -> None:
    logo = Attachment("image001.png", "image/png", _png(400, 60), inline=True)
    a = mk("A", "Any update on our quote?", atts=[logo])
    b = mk("B", "Can you send tracking for PO 5521?", hours=48, atts=[logo])
    assert find_duplicates([a, b]) == {}


def test_too_little_content_is_not_duplicate() -> None:
    a = mk("A", "Thanks!")
    b = mk("B", "Thanks!", hours=2)
    assert find_duplicates([a, b]) == {}


def test_same_message_id_is_duplicate() -> None:
    a = mk("A", "Thanks!", mid="<same@x>")
    b = mk("B", "Thanks!", hours=0, mid="<same@x>")
    assert find_duplicates([a, b]) == {"B": "A"}  # same date -> id order decides


def test_third_copy_points_to_the_first() -> None:
    a = mk("A", ITEMS, atts=[PDF])
    b = mk("B", ITEMS, hours=1, atts=[PDF])
    c = mk("C", ITEMS, hours=2, atts=[PDF])
    assert find_duplicates([c, b, a]) == {"B": "A", "C": "A"}


# ---------------------------------------------------------------- thread parents


def test_in_reply_to_and_references_pick_inbox_parent() -> None:
    a = mk("A", ITEMS, mid="<a@x>")
    b = mk("B", "make line 1 five", hours=2, irt="<a@x>", refs="<a@x>", subject="Re: RFQ 100")
    c = mk("C", "and drop line 2", hours=3, irt="<zzz@ours>", refs="<a@x> <b@x> <zzz@ours>",
           mid="<c@x>", subject="Re: RFQ 100")
    b.headers["message_id"] = "<b@x>"
    assert find_parents([a, b, c]) == {"B": "A", "C": "B"}  # nearest referenced inbox message


def test_reply_to_message_not_in_inbox_has_no_parent() -> None:
    b = mk("B", "go ahead with 1-3", irt="<quote@ridgeline-supply.example>", subject="Re: Quote Q-26-1")
    assert find_parents([b]) == {}


def test_subject_fallback_needs_prefix_and_same_party() -> None:
    a = mk("A", ITEMS, subject="Pricing - pump skid")
    b = mk("B", "change line 1", hours=2, subject="RE: Pricing - pump skid")  # headers dropped
    c = mk("C", "new list", hours=3, subject="Pricing - pump skid")  # no prefix -> no fallback
    d = mk("D", "x", hours=4, subject="Re: Pricing - pump skid", sender="z@stranger.example")
    assert find_parents([a, b, c, d]) == {"B": "A"}


def test_norm_subject() -> None:
    assert norm_subject("RE: FW: Resend:  Pricing  - Skid") == "pricing - skid"
    assert norm_subject("Fwd[2]: x") == "x"


# ---------------------------------------------------------------- pipeline


def test_pipeline_duplicate_gets_no_lines_and_link(tmp_path: Path) -> None:
    from email.message import EmailMessage

    def write(name: str, date: str, subject: str) -> None:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"], m["Date"] = "b@cust.example", "rfq@ridgeline-supply.example", subject, date
        m["Message-ID"] = f"<{name}@cust.example>"
        m.set_content(ITEMS)
        m.add_attachment(b"Qty,Item\n4,tee\n", maintype="text", subtype="csv", filename="list.csv")
        (tmp_path / f"{name}.eml").write_bytes(m.as_bytes())

    write("X2", "Tue, 03 Nov 2026 09:00:00 -0600", "RESEND: RFQ 7")  # later, but sorts first by name
    write("X1", "Mon, 02 Nov 2026 09:00:00 -0600", "RFQ 7")
    out = process_inbox(tmp_path)
    assert out["X2"]["duplicate_of"] == "X1" and out["X2"]["line_items"] == []
    assert out["X2"]["classification"] == out["X1"]["classification"]
    assert out["X1"]["duplicate_of"] is None
