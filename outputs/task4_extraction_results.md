# Task 4 — Extraction results on the five Task 1 QMSum pairs

- model: `mistral` (temperature=0, seed=0, top_k=1)
- chunking: max_tokens=1200, overlap_turns=2
- matcher: `lexical:token_f1` at threshold 0.45
- cross-chunk merging: **off** (Task 4 constraint)
- ground truth: `outputs/gap_validation_results.md` via `edia/benchmark/qmsum_ground_truth.py`
- extraction wall time this run: 0s

**Reading the numbers:** *unsupported evidence* is the hallucination rate — model quotes that do not occur in the source chunk, an objective check. *Unmatched extracted* is NOT a hallucination rate: the Task 1 tables were built to answer "did the document drop this?", not to enumerate everything the discussion contained, so an unmatched element may be a correct extraction Task 1 never tabulated. Those items are listed in the JSON for human adjudication.

| Pair | Completeness | Evidence grounded | Unsupported (hallucination) | Strict verbatim | Unmatched extracted | Records |
|---|---|---|---|---|---|---|
| QSUM_001 | 5/11 (45%) | 76/84 (90%) | 10% | 83% | 117/121 | 25 |
| QSUM_002 | 4/8 (50%) | 65/81 (80%) | 20% | 78% | 58/62 | 15 |
| QSUM_003 | 1/9 (11%) | 30/34 (88%) | 12% | 88% | 32/33 | 8 |
| QSUM_004 | 4/14 (29%) | 48/61 (79%) | 21% | 77% | 62/65 | 17 |
| QSUM_005 | 2/6 (33%) | 101/123 (82%) | 18% | 80% | 117/119 | 26 |
| **TOTAL** | **16/48 (33%)** | **320/383 (84%)** | **16%** | **80%** | **386/400** | **91** |

### QSUM_001 — missed ground-truth elements

- **alternative**: double-curved casing -- would block use of the scroll wheel
  - closest extraction (0.44): no scroll-wheel
- **rationale**: The uncurved option was considered too dull.
  - closest extraction (0.25): uncurved or flat case
- **alternative**: LCD display -- the design already had a scroll wheel, speech recognition, rubber and fancy colours
  - closest extraction (0.38): The scroll-wheel was already decided.
- **rationale**: The team already had a scroll wheel, speech recognition, rubber and fancy colours, so an LCD was not needed.
  - closest extraction (0.38): The scroll-wheel was already decided.
- **dissent**: The Project Manager leaned towards including the LCD for budget and high-tech-feel reasons and was talked out of it.
  - closest extraction (0.27): Project Manager: 'No.'
- **dissent**: The Industrial Designer argued the LCD was too much.
  - closest extraction (0.36): Industrial Designer: 'It's more robust.'

**Ungrounded quotes (fabricated text) in QSUM_001:**

- `QSUM_001_c000_d1` (decision): 'I have some points I would like to point out.'
- `QSUM_001_c001_d1` (decision): "It might not be too hard. It it shouldn't be too hard. It it shouldn't be too hard."
- `QSUM_001_c002_d6` (decision): "so you can get a really good grip on it . So you don't have to um attain much pressure to it . It's it's a lot easier ."
- `QSUM_001_c005_d1` (decision): "Okay . Yes . Well , that that that's one possibility , okay ."
- `QSUM_001_c006_d2` (decision): "The kinetic thing it's it's a possibility. It's it's more advanced, but I'm not sure you should combine it with batteries."
- `QSUM_001_c006_d2` (decision): "But that's the same with the solar cell. That's no different."
- `QSUM_001_c008_d2` (decision): 'Traditional batteries and solar can be complementary.'
- `QSUM_001_c010_d1` (rationale): "I'm I'm not so sure , I have to ask with manufacturing , but I'm I'm not sure that's what you want , because our customers specifically ask for the spongy feel , and that's what you get with rubber . So if you want the spongy feel , you need uh to make these buttons all all of rubber ."

### QSUM_002 — missed ground-truth elements

- **decision**: Kryptonite was chosen as the preferred energy source.
  - closest extraction (0.36): The team decided to use batteries as the energy source.
- **alternative**: battery
  - closest extraction (0.00): —
- **rationale**: The chip is the most expensive part regardless, so the energy source's own cost is a secondary concern.
  - closest extraction (0.30): The cost of the remote with a screen is more expensive than the regular chip and the minimal.
- **condition**: The exact price of kryptonite was never established -- the website did not give an actual cost.
  - closest extraction (0.43): Kryptonite -- no actual cost found

**Ungrounded quotes (fabricated text) in QSUM_002:**

- `QSUM_002_c000_d1` (decision): "And we'll need to custom design a circuit board"
- `QSUM_002_c001_d1` (decision): 'Conceptual User Interface . Trying to talk about , um what kind of uh how people are actually going to be using this iPod-ish remote control , based on fruit vegetable design .'
- `QSUM_002_c001_d2` (decision): 'you seem like you would need a screen .'
- `QSUM_002_c002_d1` (decision): "So basically it's just gonna be a wheel then ? And you're just gonna have to have some kind of a screen because"
- `QSUM_002_c002_d1` (decision): 'But I think the wheel goes through like a hundred channels, at least on theirs.'
- `QSUM_002_c002_d1` (decision): 'but you can quickly scroll to get channels.'
- `QSUM_002_c002_d1` (decision): "I'd think that the screen would be better, because you could have that menu option, sort of"
- `QSUM_002_c005_d1` (rationale): 'So , but {disfmarker} if we have this screen like the iPod screen ?'
- `QSUM_002_c008_d1` (decision): 'no actual cost found for Kryptonite'
- `QSUM_002_c008_d1` (dissent): 'The Industrial Designer suggested Kryptonite but no cost was found'
- `QSUM_002_c008_d2` (rationale): 'The Industrial Designer suggested a dynamo'
- `QSUM_002_c008_d2` (dissent): 'The Project Manager did not express support for a dynamo'
- `QSUM_002_c008_d3` (dissent): 'The Industrial Designer did not express support for Kryptonite'
- `QSUM_002_c009_d1` (decision): "you're gonna be working on the look and feel of the design and user interface design ."
- `QSUM_002_c009_d1` (decision): "you'll get more instructions from your personal coach ."
- `QSUM_002_c009_d2` (decision): "you'll get more instructions from your personal coach ."

### QSUM_003 — missed ground-truth elements

- **decision**: A screen menu display was adopted and only basic buttons were kept.
  - closest extraction (0.10): Discussion about simplification of symbols, LCD display, menus, and ease of use for various users, but no decision was reached.
- **alternative**: more physical buttons -- users would tamper with them; the market wants convenient browsing
  - closest extraction (0.14): Discussion about the market and international presence.
- **alternative**: flip-top design -- cost
  - closest extraction (0.33): The design was not a seagull
- **alternative**: screen menu with basic buttons
  - closest extraction (0.00): —
- **rationale**: The market wants convenient browsing rather than many buttons to tamper with.
  - closest extraction (0.15): Discussion about the market and international presence.
- **rationale**: Symbols on the interface were to be simplified.
  - closest extraction (0.12): Discussion about simplification of symbols, LCD display, menus, and ease of use for various users, but no decision was reached.
- **decision**: Lightweight plastic was temporarily set as the case material.
  - closest extraction (0.29): plastic
- **condition**: The material choice was explicitly temporary and open to revision.
  - closest extraction (0.00): —

**Ungrounded quotes (fabricated text) in QSUM_003:**

- `QSUM_003_c002_d1` (decision): "It's about seventeen, seventeen Pounds, something like that."
- `QSUM_003_c003_d1` (rationale): "When it doesn't make {disfmarker}"
- `QSUM_003_c003_d1` (rationale): "And if it's somewhat similar to what you have on mobile phone"
- `QSUM_003_c004_d1` (decision): "I think that's important."

### QSUM_004 — missed ground-truth elements

- **decision**: The pure intelligent controller concept was rejected in favour of a hybrid of the Google-style and fancy controllers with limited vocal commands.
  - closest extraction (0.32): The three concepts for the user interface of the remote control were presented: Google controller, fancy controller, and intelligent controller.
- **alternative**: Google-style controller
  - closest extraction (0.33): controller with only buttons
- **alternative**: intelligent controller (voice and gesture) -- interference, cost, language burden and unresolved hardware
  - closest extraction (0.40): controller with only voice and gesture recognition
- **rationale**: Simultaneous use by several people would cause interference.
  - closest extraction (0.18): The remote control should be easy to use.
- **rationale**: It would increase the cost.
  - closest extraction (0.18): Adding both battery and solar energy battery might slightly increase the price.
- **rationale**: It would add a language and localisation burden.
  - closest extraction (0.18): No decision was made about the language adaptation for the remote control
- **rationale**: The microphone and camera hardware questions were unresolved.
  - closest extraction (0.00): —
- **approver**: Project Manager _(soft: owner/approver, excluded from headline)_
  - closest extraction (0.00): —
- **alternative**: wood
  - closest extraction (0.29): Marketing suggested a combination of wood and rubber for the buttons.
- **decision**: Both battery and solar alimentation were adopted.
  - closest extraction (0.43): Adding both battery and solar energy battery might slightly increase the price.
- **condition**: The design would increase the production cost, but this was treated as added value that can be compensated.
  - closest extraction (0.29): It could be an added value to the remote control.

**Ungrounded quotes (fabricated text) in QSUM_004:**

- `QSUM_004_c000_d1` (decision): "So I will present the concept of user interface . Um there's three concepts in the user interface . So first one it's a Google controller . The second is a fancy controller . The last one is uh intelligent controller ."
- `QSUM_004_c001_d1` (decision): 'And mayb maybe we can have the switching mode to pass from you know voice controller to manual controllers , eh .'
- `QSUM_004_c004_d1` (decision): "But it's not the feature of the controller , that's a function of T_V_ . You can replace your T_V_ with a new T_V_ with internet browsing function ,"
- `QSUM_004_c004_d1` (rationale): 'Yeah , but we want something th that works all the time , every day , every hour , for everyone .'
- `QSUM_004_c004_d1` (rationale): "I don't see how adding speech or gesture recognition would make the remote control look more like Google . Google is simple , works fine ,"
- `QSUM_004_c006_d1` (decision): 'It can be interesting for people to have this kind of remote control with both battery and solar energy.'
- `QSUM_004_c006_d1` (rationale): 'and maybe it can attract all the ecological consumers'
- `QSUM_004_c006_d1` (decision): 'having them both will add a little bit of the price, but it will be an added value also that will be compensated,'
- `QSUM_004_c006_d2` (rationale): "it's very resistant but, you know, something wooden will be like, I don't know high class,"
- `QSUM_004_c006_d2` (rationale): 'and if you want to put fashion in electronics maybe we can try to do something with wood.'
- `QSUM_004_c008_d2` (rationale): 'maybe will attract pro-ecology consumers'
- `QSUM_004_c009_d1` (decision): "And I think we'll have to evaluate the product too."
- `QSUM_004_c009_d1` (decision): 'And remember as as I said last meeting, we really have to build a fashion remote control and uh the colour of the um the society will be really seen in the remote control.'

### QSUM_005 — missed ground-truth elements

- **decision**: An advanced chip was approved in order to support speech recognition.
  - closest extraction (0.40): advanced chip -- not chosen
- **alternative**: LCD display -- would have forced the most expensive chip
  - closest extraction (0.22): We have batteries.
- **rationale**: Marketing pushed for positioning the product on technological innovation.
  - closest extraction (0.17): The team decided to include the advanced feature in the product.
- **condition**: A newly available low-cost sensor component meant the advanced chip would not be expensive, which is what enabled the group to agree.
  - closest extraction (0.32): No information about the cost of the advanced chip.
- **approver**: Project Manager _(soft: owner/approver, excluded from headline)_
  - closest extraction (0.40): The Project Manager and Marketing did not like the color buttons idea.

**Ungrounded quotes (fabricated text) in QSUM_005:**

- `QSUM_005_c001_d1` (rationale): 'It has to be flexible because you drop your remote control very often on the ground.'
- `QSUM_005_c001_d1` (decision): "But maybe that's definitely a good idea"
- `QSUM_005_c001_d2` (rationale): 'A fancy look is the most important thing for a remote control.'
- `QSUM_005_c001_d2` (decision): 'Maybe a see-through one in a fruit front.'
- `QSUM_005_c003_d1` (decision): "But I think we should put that on top, and buttons we don't use on, in the bottom."
- `QSUM_005_c003_d1` (rationale): "But I think uh you'll use uh the switch channels buttons uh more often than the normal uh channel buttons, like one two three. So maybe we can put that on the bottom."
- `QSUM_005_c004_d1` (decision): "So it's cool."
- `QSUM_005_c004_d3` (decision): 'We have to use uh kind of flashy colors, I think.'
- `QSUM_005_c005_d1` (dissent): 'The Industrial Designer suggested making the case transparent, but the Project Manager and User Interface disagreed.'
- `QSUM_005_c007_d2` (rationale): 'The chip is the regular one .'
- `QSUM_005_c007_d3` (decision): 'The chip used in the remote control will be the regular one .'
- `QSUM_005_c009_d1` (dissent): "But uh but I think we we should bu uh put 'em on top of each other , so"
- `QSUM_005_c009_d1` (dissent): "But still the next one . Doesn't make"
- `QSUM_005_c009_d1` (dissent): "Yeah . I I think it's s so simple"
- `QSUM_005_c009_d1` (decision): 'Uh the image of the iPod .'
- `QSUM_005_c010_d1` (dissent): "I've had a lot of pictures of old ones. And all curves have already been done."
- `QSUM_005_c011_d1` (decision): 'And uh just with uh the back-lights b look will look very new .'
- `QSUM_005_c011_d1` (decision): 'Maybe maybe make the the mm the scroll wheel . Make it in in yellow or something . Just like the colours of Real Reaction .'
- `QSUM_005_c012_d1` (decision): 'So we can put all the functions of that in there.'
- `QSUM_005_c012_d1` (condition): "But we don't have any information about the cost."
- `QSUM_005_c012_d2` (decision): "But it doesn't say anything about it, does it?"
- `QSUM_005_c012_d2` (rationale): "I don't know how much, but our division has developed a new speech recognition feature, the integrated programmable sample sensor simple speaker unit."
