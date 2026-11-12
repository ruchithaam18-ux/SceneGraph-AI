"""SQLAlchemy schema for persistent, owner-scoped Screenplay Studio data.

Works with SQLite for local development and PostgreSQL for deployment.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone
from sqlalchemy import (create_engine, event, Integer, String, Text, ForeignKey, DateTime,
                        UniqueConstraint, JSON, CheckConstraint)
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship, sessionmaker


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def database_url():
    url = os.getenv('DATABASE_URL', 'sqlite:///./scenegraph.db')
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    return url


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id = mapped_column(Integer, primary_key=True)
    email = mapped_column(String(254), nullable=False, unique=True, index=True)
    display_name = mapped_column(String(100), nullable=False)
    password_hash = mapped_column(String(250), nullable=False)
    created_at = mapped_column(DateTime, default=utcnow, nullable=False)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at = mapped_column(DateTime, nullable=False)
    created_at = mapped_column(DateTime, default=utcnow, nullable=False)


class Project(Base):
    __tablename__ = 'projects'
    id = mapped_column(Integer, primary_key=True)
    owner_id = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = mapped_column(String(120), nullable=False)
    source_text = mapped_column(Text, nullable=False)
    settings = mapped_column(JSON, nullable=False, default=dict)
    schedules = mapped_column(JSON, nullable=False, default=dict)
    created_at = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    scenes = relationship('Scene', cascade='all, delete-orphan', passive_deletes=True)
    characters = relationship('Character', cascade='all, delete-orphan', passive_deletes=True)
    locations = relationship('Location', cascade='all, delete-orphan', passive_deletes=True)
    events = relationship('ContinuityEvent', cascade='all, delete-orphan', passive_deletes=True)


class Character(Base):
    __tablename__ = 'characters'
    __table_args__ = (UniqueConstraint('project_id', 'name', name='uq_character_project_name'),)
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    name = mapped_column(String(80), nullable=False)


class Location(Base):
    __tablename__ = 'locations'
    __table_args__ = (UniqueConstraint('project_id', 'name', name='uq_location_project_name'),)
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    name = mapped_column(String(100), nullable=False)


class Scene(Base):
    __tablename__ = 'scenes'
    __table_args__ = (
        UniqueConstraint('project_id','script_order',name='uq_scene_order'),
        CheckConstraint('duration_slots >= 1 AND duration_slots <= 24', name='ck_scene_duration'),
    )
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    script_order = mapped_column(Integer, nullable=False)
    heading = mapped_column(String(240), nullable=False)
    location_id = mapped_column(ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False)
    time_of_day = mapped_column(String(40), nullable=False)
    duration_slots = mapped_column(Integer, nullable=False, default=2)
    body = mapped_column(Text, nullable=False, default='')


class SceneCharacter(Base):
    __tablename__ = 'scene_characters'
    __table_args__ = (UniqueConstraint('scene_id','character_id',name='uq_scene_character'),)
    id = mapped_column(Integer, primary_key=True)
    scene_id = mapped_column(ForeignKey('scenes.id', ondelete='CASCADE'), nullable=False, index=True)
    character_id = mapped_column(ForeignKey('characters.id', ondelete='CASCADE'), nullable=False, index=True)


class ContinuityEvent(Base):
    __tablename__ = 'continuity_events'
    id = mapped_column(Integer, primary_key=True)
    project_id = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    scene_id = mapped_column(ForeignKey('scenes.id', ondelete='CASCADE'), nullable=False)
    prop = mapped_column(String(80), nullable=False)
    action = mapped_column(String(12), nullable=False)
    character = mapped_column(String(80), nullable=False, default='GLOBAL')


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id = mapped_column(Integer, primary_key=True)
    owner_id = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    project_id = mapped_column(Integer, nullable=True)
    action = mapped_column(String(64), nullable=False)
    detail = mapped_column(String(255), nullable=False, default='')
    created_at = mapped_column(DateTime, default=utcnow, nullable=False)


url = database_url()
engine = create_engine(url, pool_pre_ping=True, connect_args={'check_same_thread': False, 'timeout': 25} if url.startswith('sqlite') else {})
if url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def _sqlite_foreign_keys(dbapi_conn, connection_record):
        cursor=dbapi_conn.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_tables():
    Base.metadata.create_all(bind=engine)
