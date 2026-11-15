"""Eval-harness tests on synthetic strings only (no dev data)."""

from eval.eval import mentions, pair_lines, qty_ok, score


def test_spelling_equivalences() -> None:
    assert mentions("4in Schedule 80 pipe", "sch 80")
    assert mentions("flange, Class 300 RF", "300#")
    assert mentions("150 lb WN FLG", "flange")
    assert mentions("butt-weld 90 ELL", "bw|socket weld")
    assert mentions("NPT ball VLV", "threaded")
    assert mentions("SMLS A106B", "seamless")
    assert mentions("MI 45 elbow, galvanized", "malleable")
    assert mentions("galvanized", "galv")
    assert not mentions("sch 40 pipe", "sch 80")
    assert not mentions("carbon steel tee", "stainless")


def test_phrases_match_on_token_boundaries() -> None:
    # "sch40" must not match inside "sch400" (any spacing / punctuation)
    assert not mentions("2in sch400 pipe", "sch 40")
    assert not mentions("2in Sch 400 pipe", "sch40")
    assert mentions("2in Sch-40 pipe", "sch40")
    assert mentions("2in sch40 pipe", "schedule 40")
    # "red" must not match inside other words
    assert not mentions("reduced pressure backflow", "red")
    assert not mentions("required by friday", "red")
    assert not mentions("shredded gasket", "red")
    assert mentions("4x2 RED tee", "reducer|reducing")
    assert mentions("conc reducer 4x3", "red")
    # punctuation-joined tokens still match, plurals allowed
    assert mentions("pipe, T&C", "t&c|threaded and coupled")
    assert mentions("12 90 ELLs", "elbow")


def test_pairing_is_one_to_one() -> None:
    key = [{"raw": "10 ea 2\" tee"}, {"raw": "6 ea 3\" union"}]
    pred = [{"raw": "6 ea - 3\" union"}, {"raw": "10 ea - 2\" tee"}, {"raw": "Thanks, Bob"}]
    pairs = {(i, j) for i, j, _ in pair_lines(key, pred)}
    assert pairs == {(0, 1), (1, 0)}


def test_qty_tolerance() -> None:
    assert qty_ok({"qty": 10, "qty_tol": 0}, {"qty": 10.0})
    assert not qty_ok({"qty": 10, "qty_tol": 0}, {"qty": 11})
    assert qty_ok({"qty": 100, "qty_tol": 0.1}, {"qty": 105})
    assert qty_ok({"qty": 5, "qty_tol": None}, {"qty": 99}) is None


def test_silent_loss_and_phantom() -> None:
    key = {
        "X1": {"classification": "rfq", "needs_review": False, "line_items": [
            {"id": "X1-1", "raw": "5 ea gate valve", "qty": 5, "qty_tol": 0, "uom": "EA",
             "source": "body", "must_mention": [], "must_not_mention": []}]},
        "X2": {"classification": "vendor_quote", "needs_review": False, "line_items": []},
    }
    pred = {
        "X1": {"classification": "other", "needs_review": False, "line_items": []},
        "X2": {"classification": "rfq", "needs_review": False, "line_items": []},
    }
    s = score(key, pred)
    assert s.silent_losses == ["X1"]
    assert s.lost == ["X1"] and s.phantom == ["X2"]
