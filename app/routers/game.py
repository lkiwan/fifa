from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Game, GamePlayer, GameRound, Player, RoundQuestion, UserRoundAnswer
from app.questions import build_questions, random_footballer

router = APIRouter(prefix="/games", tags=["game"])


class CreateGame(BaseModel):
    players: list[str]


class SubmitAnswers(BaseModel):
    user_index: int
    answers: list[int]


def _current_round(db: Session, game: Game):
    rounds = sorted(game.rounds, key=lambda r: r.round_number)
    return rounds[-1] if rounds else None


def _answered_count(db: Session, round_: GameRound, player: GamePlayer):
    return (
        db.query(UserRoundAnswer)
        .filter(UserRoundAnswer.round_id == round_.id, UserRoundAnswer.game_player_id == player.id)
        .count()
    )


def _next_user(db: Session, game: Game, round_: GameRound):
    active = sorted(
        [p for p in game.players if not p.is_eliminated],
        key=lambda p: p.order_index,
    )
    q_count = len(round_.questions)
    for p in active:
        if _answered_count(db, round_, p) < q_count:
            return p.order_index
    return None


def _game_state(db: Session, game: Game):
    players = sorted(game.players, key=lambda p: p.order_index)
    round_ = _current_round(db, game)
    next_user = None
    round_complete = False

    if game.status == "finished":
        return {
            "game_id": game.id,
            "status": game.status,
            "winner": game.winner_name,
            "round_number": round_.round_number if round_ else 0,
            "players": [{"index": p.order_index, "name": p.name, "eliminated": p.is_eliminated} for p in players],
            "next_user_index": None,
            "round_complete": False,
        }

    if round_ is not None:
        next_user = _next_user(db, game, round_)
        round_complete = next_user is None

    return {
        "game_id": game.id,
        "status": game.status,
        "winner": None,
        "round_number": round_.round_number if round_ else 0,
        "players": [{"index": p.order_index, "name": p.name, "eliminated": p.is_eliminated} for p in players],
        "next_user_index": next_user,
        "round_complete": round_complete,
    }


def _create_round(db: Session, game: Game, round_number: int):
    footballer = random_footballer(db)
    if footballer is None:
        raise HTTPException(status_code=503, detail="Aucune donnée joueur. Lancez la mise à jour des données.")

    round_ = GameRound(
        game_id=game.id,
        round_number=round_number,
        footballer_id=footballer.id,
        footballer_name=footballer.name,
    )
    db.add(round_)
    db.flush()

    for q in build_questions(db, footballer, count=4):
        db.add(
            RoundQuestion(
                round_id=round_.id,
                qtype=q["qtype"],
                question=q["question"],
                choices=q["choices"],
                correct_index=q["correct_index"],
            )
        )
    db.commit()
    db.refresh(round_)
    return round_


@router.post("")
def create_game(payload: CreateGame, db: Session = Depends(get_db)):
    names = [n.strip() for n in payload.players if n.strip()]
    if len(names) < 2:
        raise HTTPException(status_code=400, detail="Il faut au moins 2 joueurs.")
    if len(names) > 12:
        raise HTTPException(status_code=400, detail="Maximum 12 joueurs.")
    if len(set(names)) != len(names):
        raise HTTPException(status_code=400, detail="Les noms doivent être uniques.")

    game = Game(status="active")
    db.add(game)
    db.flush()

    for i, name in enumerate(names):
        db.add(GamePlayer(game_id=game.id, name=name, order_index=i))

    _create_round(db, game, 1)

    return {"game_id": game.id}


@router.get("/{game_id}")
def game_state(game_id: int, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    return _game_state(db, game)


@router.get("/{game_id}/turn")
def get_turn(game_id: int, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    if game.status == "finished":
        raise HTTPException(status_code=409, detail="Partie terminée")

    round_ = _current_round(db, game)
    next_idx = _next_user(db, game, round_) if round_ else None
    if next_idx is None:
        return {"round_complete": True}

    player_obj = {p.order_index: p for p in game.players}[next_idx]
    footballer = round_.footballer

    questions = [
        {
            "id": q.id,
            "qtype": q.qtype,
            "question": q.question,
            "choices": q.choices,
        }
        for q in round_.questions
    ]

    return {
        "round_number": round_.round_number,
        "user_index": next_idx,
        "user_name": player_obj.name,
        "pass_phone_to": player_obj.name,
        "footballer": {
            "name": footballer.name,
            "club": footballer.club,
            "position": footballer.position,
            "age": footballer.age,
            "nationalities": footballer.nationalities,
            "market_value": footballer.market_value,
            "portrait_url": footballer.portrait_url,
        },
        "questions": questions,
    }


@router.post("/{game_id}/answers")
def submit_answers(game_id: int, payload: SubmitAnswers, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable")

    round_ = _current_round(db, game)
    player_obj = db.query(GamePlayer).filter_by(game_id=game_id, order_index=payload.user_index).first()
    if player_obj is None:
        raise HTTPException(status_code=400, detail="Joueur inconnu")

    # Must be this user's turn
    next_idx = _next_user(db, game, round_) if round_ else None
    if next_idx is None:
        raise HTTPException(status_code=409, detail="La manche est déjà complète")
    if next_idx != payload.user_index:
        raise HTTPException(status_code=409, detail="Ce n'est pas le tour de ce joueur")

    questions = sorted(round_.questions, key=lambda q: q.id)
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Le nombre de réponses ne correspond pas aux questions")

    for q, chosen in zip(questions, payload.answers):
        if not (0 <= chosen < len(q.choices)):
            raise HTTPException(status_code=400, detail="Choix invalide")
        db.add(
            UserRoundAnswer(
                round_id=round_.id,
                game_player_id=player_obj.id,
                question_id=q.id,
                chosen_index=chosen,
                is_correct=(chosen == q.correct_index),
            )
        )
    db.commit()

    return {"next_user_index": _next_user(db, game, round_)}


@router.get("/{game_id}/reveal")
def reveal(game_id: int, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable")

    round_ = _current_round(db, game)
    if round_ is None or _next_user(db, game, round_) is not None:
        raise HTTPException(status_code=409, detail="La manche n'est pas encore terminée")

    footballer = round_.footballer
    questions = sorted(round_.questions, key=lambda q: q.id)
    players = sorted(game.players, key=lambda p: p.order_index)

    q_data = []
    for q in questions:
        q_data.append({
            "id": q.id,
            "qtype": q.qtype,
            "question": q.question,
            "choices": q.choices,
            "correct_index": q.correct_index,
            "correct_answer": q.choices[q.correct_index],
        })

    user_results = []
    for p in players:
        answers = (
            db.query(UserRoundAnswer)
            .filter(UserRoundAnswer.round_id == round_.id, UserRoundAnswer.game_player_id == p.id)
            .all()
        )
        by_q = {a.question_id: a for a in answers}
        user_answers = []
        score = 0
        for q in questions:
            a = by_q.get(q.id)
            if a is None:
                user_answers.append({"question_id": q.id, "chosen_index": None, "is_correct": False})
            else:
                user_answers.append({"question_id": q.id, "chosen_index": a.chosen_index, "is_correct": a.is_correct})
                if a.is_correct:
                    score += 1
        user_results.append({
            "index": p.order_index,
            "name": p.name,
            "eliminated": p.is_eliminated,
            "score": score,
            "answers": user_answers,
        })

    return {
        "round_number": round_.round_number,
        "footballer": {
            "name": footballer.name,
            "club": footballer.club,
            "position": footballer.position,
            "portrait_url": footballer.portrait_url,
        },
        "questions": q_data,
        "results": user_results,
    }


@router.post("/{game_id}/next-round")
def next_round(game_id: int, db: Session = Depends(get_db)):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable")

    round_ = _current_round(db, game)
    if round_ is None or _next_user(db, game, round_) is not None:
        raise HTTPException(status_code=409, detail="La manche n'est pas encore terminée")

    round_.is_complete = True

    # Compute scores for this round
    players = sorted(game.players, key=lambda p: p.order_index)
    active = [p for p in players if not p.is_eliminated]
    q_count = len(round_.questions)
    scores = {}
    for p in active:
        n = (
            db.query(UserRoundAnswer)
            .filter(
                UserRoundAnswer.round_id == round_.id,
                UserRoundAnswer.game_player_id == p.id,
                UserRoundAnswer.is_correct.is_(True),
            )
            .count()
        )
        scores[p.id] = n
    db.commit()

    if not active:
        raise HTTPException(status_code=409, detail="Aucun joueur actif")

    min_score = min(scores.values())
    losers = [p for p in active if scores[p.id] == min_score]

    if len(losers) < len(active):
        for p in losers:
            p.is_eliminated = True
            p.round_out = round_.round_number
    db.commit()

    remaining = [p for p in active if not p.is_eliminated]

    if len(remaining) == 1:
        game.status = "finished"
        game.winner_name = remaining[0].name
        db.commit()
    else:
        _create_round(db, game, round_.round_number + 1)

    return _game_state(db, game)