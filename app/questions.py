import random

from app.models import Player


def _fmt_euro(millions):
    if millions is None:
        return None
    if millions >= 1000:
        return f"{millions / 1000:.2f}".replace(".", ",") + " Mrd. €"
    return f"{millions:.2f}".replace(".", ",") + " Mio. €"


def _fmt_height(cm):
    if not cm:
        return None
    return f"{cm / 100:.2f}".replace(".", ",") + " m"


def _distractors_int(correct, offsets, minimum=None):
    cand = set()
    random.shuffle(offsets)
    for off in offsets:
        v = correct + off
        if minimum is not None and v < minimum:
            continue
        if v <= 0 or v == correct:
            continue
        cand.add(v)
        if len(cand) >= 3:
            break
    return list(cand)


def _distractors_money(correct):
    cand = set()
    for mult in (0.8, 0.85, 0.9, 0.95, 1.05, 1.1, 1.15, 1.2, 1.25):
        v = round(correct * mult, 1)
        if v <= 0 or v == correct:
            continue
        cand.add(v)
    return list(cand)


def _distinct_values(session, attr, exclude):
    vals = set()
    for obj in session.query(Player).all():
        v = getattr(obj, attr, None)
        if v is None:
            continue
        if isinstance(v, list):
            vals.update(v)
        else:
            vals.add(v)
    vals.discard(exclude)
    return vals


def _make_choices(correct_label, distractors):
    pool = list(distractors) + [correct_label]
    # ensure unique labels
    uniq = []
    seen = set()
    for x in pool:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    if len(uniq) < 4:
        filler = 1
        while len(uniq) < 4:
            extra = f"{correct_label} ({filler})"
            if extra not in seen:
                seen.add(extra)
                uniq.append(extra)
            filler += 1
    random.shuffle(uniq)
    return uniq, uniq.index(correct_label)


def build_questions(session, player, count=4):
    qt = []

    # 1. Age
    if player.age is not None:
        correct = int(player.age)
        dist = _distractors_int(correct, [-3, -2, -1, 1, 2, 3], minimum=15)
        while len(dist) < 3:
            v = correct + len(dist) + 3
            if v >= 15 and v != correct:
                dist.append(v)
        choices, idx = _make_choices(str(correct), [str(x) for x in dist[:3]])
        qt.append({
            "qtype": "age",
            "question": f"Quel âge a {player.name} ?",
            "choices": choices,
            "correct_index": idx,
        })

    # 2. Market value
    if player.market_value_millions is not None and player.market_value_millions > 0:
        correct = round(player.market_value_millions, 1)
        dist = _distractors_money(correct)
        while len(dist) < 3:
            dist.append(round(correct * (0.9 + 0.08 * len(dist)), 1))
        choices, idx = _make_choices(_fmt_euro(correct), [_fmt_euro(x) for x in dist[:3]])
        if len(choices) >= 4:
            qt.append({
                "qtype": "market_value",
                "question": f"Quelle est la valeur marchande de {player.name} ?",
                "choices": choices,
                "correct_index": idx,
            })

    # 3. Club
    if player.club:
        others = list(_distinct_values(session, "club", player.club))
        others = random.sample(others, min(3, len(others)))
        while len(others) < 3:
            others.append("Sans club")
        choices, idx = _make_choices(player.club, others[:3])
        if len(choices) >= 4:
            qt.append({
                "qtype": "club",
                "question": f"Dans quel club joue {player.name} ?",
                "choices": choices,
                "correct_index": idx,
            })

    # 4. Nationality
    if player.nationalities:
        nat = player.nationalities[0]
        others = list(_distinct_values(session, "nationalities", nat))
        others = random.sample(others, min(3, len(others)))
        while len(others) < 3:
            others.append("Sans nationalité")
        choices, idx = _make_choices(nat, others[:3])
        if len(choices) >= 4:
            qt.append({
                "qtype": "nationality",
                "question": f"Quelle est la nationalité de {player.name} ?",
                "choices": choices,
                "correct_index": idx,
            })

    # 5. Position
    if player.position:
        others = list(_distinct_values(session, "position", player.position))
        others = random.sample(others, min(3, len(others)))
        while len(others) < 3:
            others.append("Remplaçant")
        choices, idx = _make_choices(player.position, others[:3])
        if len(choices) >= 4:
            qt.append({
                "qtype": "position",
                "question": f"À quel poste joue {player.name} ?",
                "choices": choices,
                "correct_index": idx,
            })

    # 6. Height
    if player.height_cm:
        correct = int(player.height_cm)
        dist = _distractors_int(correct, [-7, -5, -4, 4, 5, 7], minimum=140)
        while len(dist) < 3:
            v = correct + 4 + len(dist)
            if v >= 140:
                dist.append(v)
        correct_label = _fmt_height(correct)
        dist_labels = [
            _fmt_height(x) for x in dist[:3] if _fmt_height(x) and _fmt_height(x) != correct_label
        ]
        while len(dist_labels) < 3:
            v = correct + 5 + len(dist_labels)
            fl = _fmt_height(v)
            if fl and fl != correct_label:
                dist_labels.append(fl)
        choices, idx = _make_choices(correct_label, dist_labels[:3])
        if len(choices) >= 4:
            qt.append({
                "qtype": "height",
                "question": f"Quelle est la taille de {player.name} ?",
                "choices": choices,
                "correct_index": idx,
            })

    # 7. Foot
    if player.foot:
        raw = player.foot.lower()
        if "deux" in raw or "ambidextre" in raw or "both" in raw:
            correct_label = "ambidextre"
        elif raw in ("gauche", "gauche seulement", "left"):
            correct_label = "gauche"
        elif raw in ("droit", "droite", "right"):
            correct_label = "droit"
        else:
            correct_label = None
        if correct_label:
            foots = ["gauche", "droit", "ambidextre"]
            pool = list({f for f in foots})
            random.shuffle(pool)
            if len(pool) >= 3:
                qt.append({
                    "qtype": "foot",
                    "question": f"Quel est le pied fort de {player.name} ?",
                    "choices": pool,
                    "correct_index": pool.index(correct_label),
                })

    return qt[:count]


def random_footballer(session):
    players = session.query(Player).all()
    if not players:
        return None
    return random.choice(players)