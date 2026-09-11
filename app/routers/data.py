from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Player
from app.questions import random_footballer

router = APIRouter(prefix="/players", tags=["data"])


@router.get("/count")
def player_count(db: Session = Depends(get_db)):
    return {"count": db.query(Player).count()}


@router.get("/random")
def random_player(db: Session = Depends(get_db)):
    player = random_footballer(db)
    if player is None:
        raise HTTPException(status_code=404, detail="Aucun joueur en base")
    return {
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "club": player.club,
        "age": player.age,
        "nationalities": player.nationalities,
        "market_value": player.market_value,
        "portrait_url": player.portrait_url,
    }