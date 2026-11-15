# Eval vs dev answer key

| metric | value |
|---|---|
| silent_losses | 19 |
| hallucinated_lines | 0 |
| lost_requests | 20 |
| phantom_requests | 0 |
| classification | 4.2% (1/24) |
| line_recall | 0.0% (0/210) |
| line_precision | n/a |
| qty | n/a |
| uom | n/a |
| source | n/a |
| context_carried | n/a |
| links | 0.0% (0/2) |
| review_precision | n/a |
| review_recall | 0.0% (0/2) |

## Silent losses (19)

```
E001
E002
E003
E004
E005
E006
E007
E009
E010
E015
E016
E017
E018
E019
E020
E021
E022
E023
E024
```

## Classification errors (23)

```
E001: key=rfq pred=other
E002: key=rfq pred=other
E003: key=rfq pred=other
E004: key=rfq_revision pred=other
E005: key=rfq pred=other
E006: key=rfq pred=other
E007: key=rfq pred=other
E008: key=rfq pred=other
E009: key=rfq pred=other
E010: key=rfq pred=other
E011: key=vendor_quote pred=other
E012: key=status_inquiry pred=other
E013: key=auto_reply pred=other
E015: key=purchase_order pred=other
E016: key=rfq pred=other
E017: key=rfq pred=other
E018: key=rfq pred=other
E019: key=rfq pred=other
E020: key=purchase_order pred=other
E021: key=rfq pred=other
E022: key=rfq pred=other
E023: key=rfq pred=other
E024: key=rfq pred=other
```

## Missed key lines (210)

```
E001-1: '12 jts - 2" SCH 40 A53B ERW black pipe, PE'
E001-2: '(30) 2" 3000# forged threaded 90 elbow, A105'
E001-3: '(30) 2" 3000# forged threaded coupling, A105'
E001-4: '200 ft - 3/4" SCH 40 galvanized pipe, TBE'
E001-5: '4" 150# RF slip-on flange, A105 x 6'
E002-1: '10 of the 1/2 90s'
E002-2: '6 tees same size'
E002-3: 'a couple caps'
E002-4: '12 of the 3/4 couplings'
E002-5: '20 of the 3/4 close nipples'
E003-1: '1) 20 jts - 2"'
E003-2: '2) 10 jts - 3"'
E003-3: '3) 6 jts - 4"'
E003-4: '4) 12 ea - 2" 90 ell'
E003-5: '5) 8 ea - 2" tee'
E003-6: '6) 6 ea - 2" union'
E003-7: '7) 4 ea - 2" gate, bronze, 125#'
E003-8: '8) 2 ea - 2" check, swing, bronze, 125#'
E004-1: '1) 20 jts - 2"'
E004-2: '2) 14 jts - 3"'
E004-3: '3) 6 jts - 4"'
E004-4: '4) 12 ea - 2" 90 ell'
E004-5: '5) 8 ea - 2" tee'
E004-6: '7) 4 ea - 2" gate, bronze, 125#'
E004-7: '8) 2 ea - 2" check, swing, bronze, 125#'
E004-8: '9) 4 ea - 2" ball, bronze, 125#'
E005-1: '1 | 12 | EA | 6" | 90 LR elbow'
E005-2: '2 | 6 | EA | 6" | 45 elbow'
E005-3: '3 | 4 | EA | 8" | 90 LR elbow'
E005-4: '4 | 4 | EA | 6" | Tee, straight'
E005-5: '5 | 3 | EA | 8" x 6" | Reducer, concentric'
E005-6: '6 | 2 | EA | 6" x 4" | Reducer, concentric, SCH 80'
E005-7: '7 | 2 | EA | 8" | Cap'
E005-8: '8 | 2 | EA | 6" | Cap'
E006-1: '2 sets of 4" 150# spiral wound gaskets, 304 SS/graphite'
E006-2: '6 sets of 6" 150# spiral wound gaskets, 304 SS/graphite'
E006-3: '1 | 7 | EA | 1/2" | WELD NECK FLANGE, STD BORE'
E006-4: '2 | 3 | EA | 3/4" | WELD NECK FLANGE, STD BORE'
E006-5: '3 | 8 | EA | 1" | WELD NECK FLANGE, STD BORE'
E006-6: '4 | 4 | EA | 1-1/4" | WELD NECK FLANGE, STD BORE'
E006-7: '5 | 9 | EA | 1-1/2" | WELD NECK FLANGE, STD BORE'
E006-8: '6 | 5 | EA | 2" | WELD NECK FLANGE, STD BORE'
E006-9: '7 | 10 | EA | 2-1/2" | WELD NECK FLANGE, STD BORE'
E006-10: '8 | 6 | EA | 3" | WELD NECK FLANGE, STD BORE'
E006-11: '9 | 2 | EA | 4" | WELD NECK FLANGE, STD BORE'
E006-12: '10 | 7 | EA | 6" | WELD NECK FLANGE, STD BORE'
E006-13: '11 | 3 | EA | 8" | WELD NECK FLANGE, STD BORE'
E006-14: '12 | 8 | EA | 10" | WELD NECK FLANGE, STD BORE'
E006-15: '13 | 4 | EA | 12" | WELD NECK FLANGE, STD BORE'
E006-16: '14 | 9 | EA | 14" | WELD NECK FLANGE, STD BORE'
E006-17: '15 | 5 | EA | 1/2" | SLIP-ON FLANGE'
E006-18: '16 | 10 | EA | 3/4" | SLIP-ON FLANGE'
E006-19: '17 | 6 | EA | 1" | SLIP-ON FLANGE'
E006-20: '18 | 2 | EA | 1-1/4" | SLIP-ON FLANGE'
E006-21: '19 | 7 | EA | 1-1/2" | SLIP-ON FLANGE'
E006-22: '20 | 3 | EA | 2" | SLIP-ON FLANGE'
E006-23: '21 | 8 | EA | 2-1/2" | SLIP-ON FLANGE'
E006-24: '22 | 4 | EA | 3" | SLIP-ON FLANGE'
E006-25: '23 | 9 | EA | 4" | SLIP-ON FLANGE'
E006-26: '24 | 5 | EA | 6" | SLIP-ON FLANGE'
E006-27: '25 | 10 | EA | 8" | SLIP-ON FLANGE'
E006-28: '26 | 6 | EA | 10" | SLIP-ON FLANGE'
E006-29: '27 | 2 | EA | 12" | SLIP-ON FLANGE'
E006-30: '28 | 7 | EA | 14" | SLIP-ON FLANGE'
E006-31: '29 | 3 | EA | 1/2" | BLIND FLANGE'
E006-32: '30 | 8 | EA | 3/4" | BLIND FLANGE'
E006-33: '31 | 4 | EA | 1" | BLIND FLANGE'
E006-34: '32 | 9 | EA | 1-1/4" | BLIND FLANGE'
E006-35: '33 | 5 | EA | 1-1/2" | BLIND FLANGE'
E006-36: '34 | 10 | EA | 2" | BLIND FLANGE'
E006-37: '35 | 6 | EA | 2-1/2" | BLIND FLANGE'
E006-38: '36 | 2 | EA | 3" | BLIND FLANGE'
E006-39: '37 | 7 | EA | 4" | BLIND FLANGE'
E006-40: '38 | 3 | EA | 6" | BLIND FLANGE'
E006-41: '39 | 8 | EA | 8" | BLIND FLANGE'
E006-42: '40 | 4 | EA | 10" | BLIND FLANGE'
E006-43: '41 | 9 | EA | 12" | BLIND FLANGE'
E006-44: '42 | 5 | EA | 14" | BLIND FLANGE'
E007-1: '8 - 2" galv 90 elbow'
E007-2: '4 - ,, tee'
E007-3: '6 - 1" x 3" galv nipple'
E007-4: '6 - 1" x 4" ,,'
E007-5: '12 - 2" galv coupling'
E007-6: '2 - 2" galv union'
E007-7: '5 jts - 2" galv pipe'
E009-1: '1 | 6 | EA | 1" | WN 150# RF'
E009-2: '2 | 4 | EA | 1-1/2" | WN 150# RF'
E009-3: '3 | 10 | EA | 2" | WN 150# RF'
E009-4: '4 | 8 | EA | 3" | WN 150# RF'
E009-5: '5 | 12 | EA | 4" | WN 150# RF'
E009-6: '6 | 6 | EA | 6" | WN 150# RF'
E009-7: '7 | 4 | EA | 8" | WN 150# RF'
E009-8: '8 | 4 | EA | 2" | SO 150# RF'
E009-9: '9 | 4 | EA | 3" | SO 150# RF'
E009-10: '10 | 6 | EA | 4" | SO 150# RF'
E009-11: '11 | 4 | EA | 6" | SO 150# RF'
E009-12: '12 | 2 | EA | 2" | BL 150# RF'
E009-13: '13 | 2 | EA | 4" | BL 150# RF'
E009-14: '14 | 2 | EA | 6" | BL 150# RF'
E009-15: '15 | 10 | EA | 1" | Spiral wound, 304/graphite, 150#'
E009-16: '16 | 6 | EA | 1-1/2" | Spiral wound, 304/graphite, 150#'
E009-17: '17 | 20 | EA | 2" | Spiral wound, 304/graphite, 150#'
E009-18: '18 | 12 | EA | 3" | Spiral wound, 304/graphite, 150#'
E009-19: '19 | 16 | EA | 4" | Spiral wound, 304/graphite, 150#'
E009-20: '20 | 8 | EA | 6" | Spiral wound, 304/graphite, 150#'
E009-21: '21 | 4 | EA | 8" | Spiral wound, 304/graphite, 150#'
E009-22: '22 | 2 | EA | 10" | Spiral wound, 304/graphite, 150#'
E009-23: '23 | 32 | EA | 1/2" x 3" | B7 w/ 2 heavy hex nuts'
E009-24: '24 | 24 | EA | 5/8" x 3-1/4" | B7 w/ 2 heavy hex nuts'
E009-25: '25 | 16 | EA | 5/8" x 3-1/2" | B7 w/ 2 heavy hex nuts'
E009-26: '26 | 48 | EA | 3/4" x 4" | B7 w/ 2 heavy hex nuts'
E009-27: '27 | 24 | EA | 3/4" x 4-1/4" | B7 w/ 2 heavy hex nuts'
E009-28: '28 | 32 | EA | 3/4" x 4-1/2" | B7 w/ 2 heavy hex nuts'
E009-29: '29 | 16 | EA | 7/8" x 5" | B7 w/ 2 heavy hex nuts'
E009-30: '30 | 16 | EA | 7/8" x 5-1/4" | B7 w/ 2 heavy hex nuts'
E009-31: '31 | 16 | EA | 1" x 5-3/4" | B7 w/ 2 heavy hex nuts'
E009-32: '32 | 8 | EA | 1" x 6" | B7 w/ 2 heavy hex nuts'
E010-1: '40 | EA | 1/2"-13 x 2" hex cap screw, Gr 5 zinc'
E010-2: '40 | EA | 1/2"-13 hex nut, zinc'
E010-3: '200 | FT | 1-5/8" strut channel, 12 ga, pre-galv'
E010-4: '3 | BX | 1/2" channel spring nuts, galv'
E010-5: '24 | EA | 2" pipe clamp, galv'
E010-6: '12 | EA | 3/4"-10 all-thread rod, 6 ft'
E015-1: '1 | 210 | FT | 2" SCH 80 SMLS A106B pipe, PE, random lengths | 11.85 | 2,488.50'
E015-2: '2 | 24 | EA | 2" 90 deg elbow, LR, BW, SCH 80, A234 WPB | 14.20 | 340.80'
E015-3: '3 | 16 | EA | 2" WN flange, 300# RF, A105, SCH 80 bore | 31.75 | 508.00'
E015-4: '4 | 16 | EA | 2" spiral wound gasket, 316/graphite, 300#, w/ inner ring | 6.40 | 102.40'
E015-5: '5 | 64 | EA | Stud bolt B7, 5/8"-11 x 3-3/4", w/ 2 heavy hex nuts | 1.85 | 118.40'
E015-6: '6 | 6 | EA | 2" gate valve, 300# RF, A216 WCB, bolted bonnet | 412.00 | 2,472.00'
E016-1: '60 | FT | 1-1/2" | Pipe, SCH 80, A106B SMLS, PE'
E016-2: '12 | EA | 1-1/2" | 90 elbow, SW, 3000#, A105'
E016-3: '6 | EA | 1-1/2" | Tee, SW, 3000#, A105'
E016-4: '8 | EA | 1-1/2" | Union, SW, 3000#, A105'
E016-5: '4 | EA | 1-1/2" | Gate valve, 800#, SW, A105'
E016-6: '2 | EA | 1-1/2" | Y-strainer, 800#, SW, A105'
E018-1: '8 Weld neck flange, 150# RF, A105, STD bore 4"'
E018-2: '12 90 deg elbow, LR, BW, SCH 40, A234 WPB 4"'
E018-3: '8 Spiral wound gasket, 304/graphite, 150# 4"'
E018-4: '32 Stud bolt, B7, 4-1/2" long, w/ 2 heavy hex nuts 3/4"'
E018-5: '6 Eccentric reducer, BW, SCH 40, A234 WPB 6" x 4"'
E018-6: '12 rolls PTFE thread tape, white, heavy duty N/A'
E019-1: '10 jts | 2" | PE'
E019-2: '6 jts | 3" | PE'
E019-3: '4 jts | 4" | BE'
E019-4: '8 jts | 1" | PE'
E019-5: '24 | 1" | 90 elbow'
E019-6: '12 | 1" | Tee'
E019-7: '30 | 3/4" | Coupling, full'
E019-8: '16 | 1/2" | Union'
E019-9: '20 | 2" | Half coupling'
E020-1: '1. 8 EA - 3" 150# RF weld neck flange, A105, STD bore - $38.60 ea'
E020-2: '2. 120 FT - 3" SCH 40 A53B ERW pipe, PE - $7.95/ft'
E020-3: '4. 16 EA - 3" 90 deg LR elbow, BW, SCH 40, A234 WPB - $9.35 ea'
E021-1: '1 | 420 | FT | 1/2" | PE'
E021-2: '2 | 300 | FT | 3/4" | PE'
E021-3: '3 | 600 | FT | 1" | PE'
E021-4: '4 | 240 | FT | 1-1/4" | PE'
E021-5: '5 | 360 | FT | 1-1/2" | PE'
E021-6: '6 | 500 | FT | 2" | PE'
E021-7: '7 | 180 | FT | 2-1/2" | PE'
E021-8: '8 | 320 | FT | 3" | PE'
E021-9: '9 | 140 | FT | 4" | PE'
E021-10: '10 | 80 | FT | 6" | PE'
E021-11: '11 | 120 | FT | 1/2" | TOE'
E021-12: '12 | 160 | FT | 3/4" | TOE'
E021-13: '13 | 200 | FT | 1" | TOE'
E021-14: '14 | 100 | FT | 1-1/2" | TOE'
E021-15: '15 | 140 | FT | 2" | TOE'
E021-16: '16 | 60 | FT | 3" | BE'
E021-17: '17 | 40 | FT | 4" | BE'
E021-18: '18 | 20 | FT | 6" | BE'
E021-19: '1 | 9 | EA | 1/2" | 90 Elbow'
E021-20: '2 | 16 | EA | 3/4" | 90 Elbow'
E021-21: '3 | 23 | EA | 1" | 90 Elbow'
E021-22: '4 | 30 | EA | 1-1/4" | 90 Elbow'
E021-23: '5 | 6 | EA | 1-1/2" | 90 Elbow'
E021-24: '6 | 13 | EA | 2" | 90 Elbow'
E021-25: '7 | 20 | EA | 1/2" | 45 Elbow'
E021-26: '8 | 27 | EA | 3/4" | 45 Elbow'
E021-27: '9 | 34 | EA | 1" | 45 Elbow'
E021-28: '10 | 10 | EA | 1-1/4" | 45 Elbow'
E021-29: '11 | 17 | EA | 1-1/2" | 45 Elbow'
E021-30: '12 | 24 | EA | 2" | 45 Elbow'
E021-31: '13 | 31 | EA | 1/2" | Tee'
E021-32: '14 | 7 | EA | 3/4" | Tee'
E021-33: '15 | 14 | EA | 1" | Tee'
E021-34: '16 | 21 | EA | 1-1/4" | Tee'
E021-35: '17 | 28 | EA | 1-1/2" | Tee'
E021-36: '18 | 35 | EA | 2" | Tee'
E021-37: '19 | 11 | EA | 1/2" | Coupling'
E021-38: '20 | 18 | EA | 3/4" | Coupling'
E021-39: '21 | 25 | EA | 1" | Coupling'
E021-40: '22 | 32 | EA | 1-1/4" | Coupling'
E021-41: '23 | 8 | EA | 1-1/2" | Coupling'
E021-42: '24 | 15 | EA | 2" | Coupling'
E021-43: '25 | 22 | EA | 1/2" | Cap'
E021-44: '26 | 29 | EA | 3/4" | Cap'
E021-45: '27 | 36 | EA | 1" | Cap'
E021-46: '28 | 12 | EA | 1-1/4" | Cap'
E021-47: '29 | 19 | EA | 1-1/2" | Cap'
E021-48: '30 | 26 | EA | 2" | Cap'
E021-49: '31 | 33 | EA | 1/2" | Union'
E021-50: '32 | 9 | EA | 3/4" | Union'
E023-1: 'MODEL: HV-800-FGS'
E024-1: '10 | 90° elbow | 1/2″'
E024-2: '6 | 45° elbow | 1/2″'
E024-3: '8 | Tee | 3/4″'
E024-4: '12 | Coupling, full | 1/2″'
E024-5: '4 | Union | 1/2″'
E024-6: '6 | Hex head plug | 3/4″'
```

## Link errors (2)

```
E004.revises: key=E003 pred=None
E008.duplicate_of: key=E006 pred=None
```

## needs_review errors (2)

```
E017: key=True pred=False reason=None
E022: key=True pred=False reason=None
```
