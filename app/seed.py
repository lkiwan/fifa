import logging

from scraper import scrape_all

from app.database import SessionLocal
from app.models import Player

logger = logging.getLogger("fifa.seed")

# Fields explicitly mapped to typed columns; everything else goes to `extra`
KNOWN_FIELDS = {
    "rank", "name", "player_id", "profile_url", "position", "age", "age_int",
    "nationalities", "club", "club_url", "market_value", "market_value_millions",
    "portrait_url", "full_name", "birth_place", "height_cm", "foot",
    "positions_detail", "current_league", "extra",
}


def player_from_dict(data):
    data = dict(data)
    age = data.get("age_int") or None
    if age is None and data.get("age"):
        try:
            age = int(data.get("age"))
        except (TypeError, ValueError):
            age = None

    result = {
        "player_id": str(data.get("player_id", "")),
        "rank": _int_or_none(data.get("rank")),
        "name": data.get("name"),
        "position": data.get("position"),
        "age": age,
        "nationalities": data.get("nationalities") or None,
        "club": data.get("club"),
        "club_url": data.get("club_url"),
        "market_value": data.get("market_value"),
        "market_value_millions": data.get("market_value_millions"),
        "portrait_url": data.get("portrait_url"),
        "profile_url": data.get("profile_url"),
        "full_name": data.get("full_name") or data.get("name"),
        "birth_date": data.get("Naissance (âge)") or data.get("birth_date"),
        "birth_place": data.get("birth_place") or data.get("Lieu de naissance"),
        "height_cm": data.get("height_cm"),
        "foot": data.get("foot") or data.get("Pied"),
        "positions_detail": data.get("positions_detail"),
        "agent": data.get("Agent du joueur") or data.get("Agents"),
        "contract_until": data.get("Contrat jusqu'à"),
        "current_league": data.get("current_league"),
        "extra": {k: v for k, v in data.items() if k not in KNOWN_FIELDS},
    }
    return result


def _int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def upsert_players(db, players):
    seen = set()
    for item in players:
        rec = player_from_dict(item)
        pid = rec.get("player_id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        obj = db.query(Player).filter(Player.player_id == pid).first()
        if obj is None:
            obj = Player(player_id=pid)
            db.add(obj)
            db.flush()
        for key, value in rec.items():
            if key == "player_id":
                continue
            setattr(obj, key, value)
    db.commit()


def update_from_web(scrape_profiles=True, max_pages=None):
    players = scrape_all(
        max_pages=max_pages,
        scrape_profiles=scrape_profiles,
        output_dir=None,
        save_files=False,
    )
    if not players:
        logger.warning("Scraper returned no players.")
        return 0

    db = SessionLocal()
    try:
        upsert_players(db, players)
    finally:
        db.close()

    logger.info("Upserted %s players into database.", len(players))
    return len(players)


def count_players():
    db = SessionLocal()
    try:
        return db.query(Player).count()
    finally:
        db.close()