# Krea panel prompt spec (reuse this)

Plate Press wall tokens are `CHAR1` / `CHAR2` / `CHAR3` (not `CHARACTER1` — that word paints a person). `PILOT1` still means first card.

Two files. Never mix them.

1. **shots.txt** — picture only. No dialogue. No captions.
2. **lettering.txt** — balloons only. Same slugs as the shots.

One slug per panel: `p01_name`

---

## Shot block shape

```
p01_slug
CHAR1 is NameA
CHAR2 is NameB
PROP1 is ExactObjectName
SHOT: lens and crop.
CAMERA: where we stand, where we look, who is in frame.
LOCATION: full lock, every panel.
ACTION: one verb, who does it, what they hold.
GAZE: eyes on a named thing in the frame, not the viewer.
HANDS: every visible hand, counted.
MOTION: what moves in this instant.
```

Drop HANDS or GAZE only if that panel truly has none. Do not drop LOCATION.

---

## Locks (repeat per panel, not once at the top)

The model forgets the top of the file. Restate anything that must not wander.

**Cast.** Named people only. “Exactly N people.” Name them. “No extra person. No extra arm. No extra torso at the edge.”

**Refs.** If a still is attached:

```
REFERENCE: use image1 for face, hair, body, clothes only.
Ignore background, pose, and setting.
POSE IS NEW. Do not copy image1 pose, hands, or camera.
```

**Place.** Same stamp every panel. Short and concrete.

```
LOCATION: Interior of the Red Kite, night cycle. Steel grate floor. Amber work lights. Viewport on the left.
```

If you do not lock the room, the room changes. “A ship” is not a lock. “Desert” is what you get when the room is unnamed.

**Light.** Name the practicals. Do not invent new ones mid-sequence.

**Props.** Treat an important object like a character. Same name every time. Say what it is made of. Say who is holding it. If a panel should not have it: `NO PROP1 in this frame.`

---

## Language that breaks the picture

Do not describe a person as: shape, form, figure, mass, silhouette, blur, smear, suggestion, pale shape, receding figure.

Write: complete person, full body, correct anatomy, in focus, face readable.

Do not describe the camera as a body arriving.  
Bad: “leans in from the far side,” “a figure at the edge,” “someone over her shoulder” when you meant the lens.  
Good: “We stand at X looking at Y. The people in frame are A and B only. Camera is empty air.”

“We stand” is fine for CAMERA. It is not fine if you then imply a third body occupies that spot.

Do not use shorthand that the model can attach to the wrong body part or the wrong person. Name the object and the hand that owns it.

```
ACTION: Caught in the instant NameA holds the chrome coupling in her right hand and seats it into the hull port.
```

Not: “the tip finds the port.”

---

## ACTION line

One beat. One instant. Named actor. Named object. Named contact.

Pattern:

`Caught in the instant [Name] [verb] [object] [where]. [Object is what]. [Who is in frame]. [Who is not].`

Do not stack three verbs. Do not describe the last panel and the next panel in the same line.

---

## HANDS

Count them. If two people are in frame, account for four hands or say which are out of frame.

A mystery hand becomes a mystery person.

---

## GAZE

Eyes on a named object or person in the shot.  
`never the viewer` if you do not want poster-facing portraits.

---

## Lettering file

Same slugs. Only speech.

```
p02_slug
NS: NAMEA: Line.
THINK: NAMEB: Line.
```

Codes: NS, NSV, NS2, OFFP, YELL, FADE, WHISP, ANN, THINK, DREAM, DARK, CAP_B, CAP_T.

`NS: NAMEA: We should move.` = speaker + balloon.  
No second colon = the whole line is inside the balloon.

No picture direction in this file.

---

## When a panel fails

Do not rewrite the episode. Change one of: CAMERA, ACTION, HANDS. Reroll that slug.

Usual causes:

| Symptom | Likely cause |
|---|---|
| Wrong room | LOCATION too short or missing |
| Same pose every shot | Ref image winning; POSE IS NEW missing |
| Object changes | Prop not named; no hand on it |
| Extra person | “far side,” “over the shoulder,” uncounted hands, camera written as a body |
| Person melts | “shape / blur / silhouette / recedes” |
| Object becomes a body part | Vague “tip / shaft / end” without “handheld [named tool]” |

---

## Sci-fi extras

Lock suit, helmet, pack, and ship the same way as faces.

```
SUIT LOCK: same rust-red flight suit, cream chest panel, teal collar ring, scarred pack. No new logos. No clean armor.
HELMET: cream and rust, teal lamp. Held / worn / racked — say which. If held, two hands on it or one. If absent: NO HELMET in this frame.
```

Background extras: `No crowd. No extra crew in the hatch.`

---

Paste this spec, then the cast list, then the source scene. Ask for shots.txt + lettering.txt only.
