"""MIME-layer tests on synthetic emails (no dev data)."""

from email.message import EmailMessage

from rfq.mime import html_to_text, parse_message, split_history


def _msg(body: str, subject: str = "hello", sender: str = "a@cust.example") -> EmailMessage:
    m = EmailMessage()
    m["From"] = sender
    m["To"] = "rfq@ridgeline-supply.example"
    m["Subject"] = subject
    m["Date"] = "Mon, 02 Nov 2026 09:00:00 -0600"
    m["Message-ID"] = "<x1@cust.example>"
    m.set_content(body)
    return m


def test_reply_on_wrote_is_quoted() -> None:
    body = "Change line 1 to 5.\n\nOn Mon, Nov 2, 2026 at 8:00 AM Bob <b@c.example> wrote:\n> 1) 4 ea valve\n> 2) 2 ea tee\n"
    cur, fwd, q = split_history(body, "Re: list")
    assert cur == "Change line 1 to 5."
    assert fwd == ""
    assert "1) 4 ea valve" in q
    assert not any(ln.startswith(">") for ln in q.splitlines())


def test_wrapped_on_wrote_line() -> None:
    body = "ok thanks\n\nOn Mon, Nov 2, 2026 at 8:00 AM Bob Smith <bob@c.example>\nwrote:\n> old\n"
    cur, _, q = split_history(body, "Re: x")
    assert cur == "ok thanks" and "old" in q


def test_outlook_header_block_reply_is_quoted() -> None:
    body = "Any update?\n\nFrom: Sam\nSent: Friday, Oct 30, 2026 10:00 AM\nTo: RFQ Desk\nSubject: RFQ\n\n6 ea flange\n"
    cur, fwd, q = split_history(body, "RE: RFQ")
    assert cur == "Any update?" and fwd == "" and "6 ea flange" in q


def test_forward_is_forwarded_not_quoted() -> None:
    body = (
        "Please quote this.\n\n-----Original Message-----\nFrom: Cust <c@x.example>\n"
        "Sent: Monday\nTo: Rep\nSubject: list\n\n10 ea tee\n\n"
        "On Sun, Nov 1, 2026 at 9:00 AM Rep <r@y.example> wrote:\n> older thread\n"
    )
    cur, fwd, q = split_history(body, "FW: list")
    assert cur == "Please quote this."
    assert fwd.startswith("10 ea tee") and "From:" not in fwd
    assert "older thread" in q and "older thread" not in fwd


def test_original_message_in_plain_reply_is_quoted() -> None:
    body = "thanks\n\n-----Original Message-----\nFrom: Rep\nSent: Mon\nTo: c\nSubject: q\n\nour quote\n"
    _, fwd, q = split_history(body, "RE: q")
    assert fwd == "" and "our quote" in q


def test_gmail_forward_marker() -> None:
    body = "fyi\n\n---------- Forwarded message ---------\nFrom: X <x@x.example>\nDate: Mon\nSubject: s\nTo: y\n\n3 ea union\n"
    _, fwd, _ = split_history(body, "something")
    assert fwd == "3 ea union"


def test_html_table_rows_and_blockquote() -> None:
    html = (
        "<p>Please quote</p><table><tr><th colspan=2>ALL SCH 80</th></tr>"
        "<tr><td>4</td><td>2&quot; tee</td></tr></table>"
        "<blockquote>old line</blockquote><img src='cid:logo1' alt='ACME'>"
    )
    t = html_to_text(html)
    assert "ALL SCH 80" in t and '4 | 2" tee' in t
    assert "> old line" in t
    assert "[image: logo1 alt='ACME']" in t


def test_html_with_table_beats_flattened_text() -> None:
    m = _msg("Qty\nItem\n4\ntee\n")
    m.add_alternative("<table><tr><td>Qty</td><td>Item</td></tr><tr><td>4</td><td>tee</td></tr></table>", subtype="html")
    e = parse_message(m.as_bytes(), "T1")
    assert e.body_kind == "html" and "4 | tee" in e.body


def test_inline_image_alt_and_attachments() -> None:
    m = _msg("see sheet [cid:img1]")
    m.add_alternative("<p>see sheet</p><img src='cid:img1' alt='Screenshot'>", subtype="html")
    html_part = m.get_payload()[1]
    html_part.add_related(b"\x89PNG fake", maintype="image", subtype="png", cid="<img1>", filename="image001.png")
    m.add_attachment(b"a,b\n1,2\n", maintype="text", subtype="csv", filename="list.csv")
    e = parse_message(m.as_bytes(), "T2")
    names = {a.filename: a for a in e.attachments}
    assert set(names) == {"image001.png", "list.csv"}
    assert names["image001.png"].inline and names["image001.png"].content_id == "img1"
    assert e.image_alts["img1"] == "Screenshot"
    assert names["list.csv"].data == b"a,b\n1,2\n"


def test_nested_rfc822_is_an_attachment() -> None:
    inner = _msg("10 ea elbow", subject="original")
    outer = _msg("Delivery failed", subject="Undeliverable", sender="MAILER-DAEMON@mx1.ridgeline-supply.example")
    outer.add_attachment(inner)
    e = parse_message(outer.as_bytes(), "T3")
    assert not e.internal  # a mail server subdomain is not one of our reps
    att = [a for a in e.attachments if a.mime == "message/rfc822"]
    assert len(att) == 1
    assert "10 ea elbow" in parse_message(att[0].data, "T3-inner").body


def test_internal_sender() -> None:
    e = parse_message(_msg("fw", sender="Rep <rep@ridgeline-supply.example>").as_bytes(), "T4")
    assert e.internal and e.sender == "rep@ridgeline-supply.example"


def test_bad_charset_and_bad_date_do_not_raise() -> None:
    raw = (
        b"From: a@b.example\r\nSubject: x\r\nDate: not a date\r\n"
        b"Content-Type: text/plain; charset=x-unknown-charset\r\n\r\n12 ea tee \xff\xfe\r\n"
    )
    e = parse_message(raw, "T5")
    assert "12 ea tee" in e.body and e.date is None
