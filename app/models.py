from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    player_id = Column(String(32), unique=True, index=True)
    rank = Column(Integer, nullable=True)
    name = Column(String(255))
    position = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    nationalities = Column(JSON, nullable=True)
    club = Column(String(255), nullable=True)
    club_url = Column(String(512), nullable=True)
    market_value = Column(String(64), nullable=True)
    market_value_millions = Column(Float, nullable=True)
    portrait_url = Column(String(512), nullable=True)
    profile_url = Column(String(512), nullable=True)
    full_name = Column(String(255), nullable=True)
    birth_date = Column(String(128), nullable=True)
    birth_place = Column(String(255), nullable=True)
    height_cm = Column(Integer, nullable=True)
    foot = Column(String(32), nullable=True)
    positions_detail = Column(JSON, nullable=True)
    agent = Column(String(255), nullable=True)
    contract_until = Column(String(64), nullable=True)
    current_league = Column(String(128), nullable=True)
    extra = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    status = Column(String(16), default="active")
    winner_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")
    rounds = relationship("GameRound", back_populates="game", cascade="all, delete-orphan")


class GamePlayer(Base):
    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    name = Column(String(255))
    order_index = Column(Integer)
    is_eliminated = Column(Boolean, default=False)
    round_out = Column(Integer, nullable=True)

    game = relationship("Game", back_populates="players")


class GameRound(Base):
    __tablename__ = "game_rounds"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    round_number = Column(Integer)
    footballer_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    footballer_name = Column(String(255), nullable=True)
    is_complete = Column(Boolean, default=False)

    game = relationship("Game", back_populates="rounds")
    footballer = relationship("Player")
    questions = relationship("RoundQuestion", back_populates="round", cascade="all, delete-orphan")


class RoundQuestion(Base):
    __tablename__ = "round_questions"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("game_rounds.id"))
    qtype = Column(String(32))
    question = Column(Text)
    choices = Column(JSON)
    correct_index = Column(Integer)

    round = relationship("GameRound", back_populates="questions")


class UserRoundAnswer(Base):
    __tablename__ = "user_round_answers"

    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey("game_rounds.id"))
    game_player_id = Column(Integer, ForeignKey("game_players.id"))
    question_id = Column(Integer, ForeignKey("round_questions.id"))
    chosen_index = Column(Integer, nullable=True)
    is_correct = Column(Boolean)