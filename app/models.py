from flask_sqlalchemy import SQLAlchemy  # Importálás közvetlenül a flask_sqlalchemy-ból
from datetime import datetime
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin
import bcrypt
from app import db 
import enum


# Kapcsolótáblák
class ClubSport(db.Model):
    __tablename__ = 'clubs_sports'
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    sport_id = db.Column(db.Integer, db.ForeignKey('sports.id'), nullable=False)

    club = db.relationship('Club', backref=db.backref('club_sports', lazy=True))
    sport = db.relationship('Sport', backref=db.backref('club_sports', lazy=True))

class AthleteParent(db.Model):
    __tablename__ = 'athletes_parents'
    id = db.Column(db.Integer, primary_key=True)
    athlete_id = db.Column(db.Integer, db.ForeignKey('athletes.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=False)

    athlete = db.relationship('Athlete', backref=db.backref('parent_relationships', lazy=True))
    parent = db.relationship('Parent', backref=db.backref('child_relationships', lazy=True))


# Tábla modellek:
class GenderEnum(enum.Enum):
    FERFI = 'Férfi'
    NO = 'Nő'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    birth_year = db.Column(db.Date, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    gender = db.Column(db.Enum('Férfi', 'Nő'), nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
    # Jelszó hash-elése
    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Jelszó ellenőrzése
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.email}>'
    
    # Flask-Login által megkövetelt metódusok
    def get_id(self):
        return str(self.id)  # Stringként kell visszaadni

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False
   


class Sport(db.Model):
    __tablename__ = 'sports'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<Sport {self.name}>'


class Club(db.Model):
    __tablename__ = 'clubs'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    short_name = db.Column(db.String(40))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    
    def __repr__(self):
        return f'<Club {self.full_name}>'


class Leader(db.Model):
    __tablename__ = 'leaders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('leaders', lazy=True))
    club = db.relationship('Club', backref=db.backref('leaders', lazy=True))

    def __repr__(self):
        return f'<Leader {self.full_name}>'

class Coach(db.Model):
    __tablename__ = 'coaches'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    club_sport_id = db.Column(db.Integer, db.ForeignKey('clubs_sports.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('coaches', lazy=True))
    club_sport = db.relationship('ClubSport', backref=db.backref('coaches', lazy=True))

    def __repr__(self):
        return f'<Coach {self.user.email}>'


class Parent(db.Model):
    __tablename__ = 'parents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    coach_id = db.Column(db.Integer, db.ForeignKey('coaches.id'), nullable=False)  # Új idegen kulcs

    user = db.relationship('User', backref=db.backref('parent', uselist=False))
    coach = db.relationship('Coach', backref=db.backref('parents', lazy=True))  # Új kapcsolat

    def __repr__(self):
        return f'<Parent {self.user.email}>'

class Athlete(db.Model):
    __tablename__ = 'athletes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    coach_id = db.Column(db.Integer, db.ForeignKey('coaches.id'), nullable=False)
    

    user = db.relationship('User', backref=db.backref('athlete', uselist=False))
    coach = db.relationship('Coach', backref=db.backref('athletes', lazy=True))
    

    def __repr__(self):
        return f'<Athlete {self.user.email}>'

