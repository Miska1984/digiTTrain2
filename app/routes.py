from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import RegistrationForm, LoginForm, ProfileForm, CreateClubForm, CreateRoleLeaderForm, CreateRoleCoachForm, CreateRoleParentForm, CreateRoleAthleteForm, AddParentsForm, UpgradeClubForm
from app.models import User, db, Club, Leader, Sport, Coach, ClubSport, Parent, Athlete, AthleteParent
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy  # Importálás közvetlenül a flask_sqlalchemy-ból
from app import bcrypt
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete
from dateutil.relativedelta import relativedelta
from datetime import date, datetime

# Blueprint létrehozása
bp = Blueprint('routes', __name__)

def check_age(user):
    if user.birth_year:
        birth_date = datetime.strptime(str(user.birth_year), '%Y-%m-%d').date()  # Átalakítás date típusúvá
        age = relativedelta(date.today(), birth_date).years
        if age < 18:
            flash('Ehhez az oldalhoz 18 éven felüliek férhetnek hozzá!', 'danger')
            return True  # 18 év alatti
    return False  # 18 éves vagy idősebb

def get_user_roles(user_id):
    roles = []

    # Inicializáljuk a változókat
    has_parent = False
    parent_name = None
    coach_name = None
    children = []
    sports = []  # Sportágak listájának inicializálása

    athlete = Athlete.query.filter_by(user_id=user_id).first()
    if athlete:
        # ... (sportoló szerepkör adatai)
        roles.append({
            'name': 'Sportoló',
            'details': {
                'club': athlete.coach.club_sport.club.short_name if athlete.coach else None,
                'sport': athlete.coach.club_sport.sport.name if athlete.coach else None,
                'coach_name': coach_name,
                'parent_name': parent_name
            },
            'has_parent': has_parent,
            'athlete': athlete,
            'age': relativedelta(date.today(), datetime.strptime(str(current_user.birth_year), '%Y-%m-%d').date()).years if current_user.birth_year else None
        })

    coach = Coach.query.filter_by(user_id=user_id).first()
    if coach:
        roles.append({
            'name': 'Edző',
            'details': {
                'club': coach.club_sport.club.short_name if coach.club_sport else None,
                'sport': coach.club_sport.sport.name if coach.club_sport else None
            }
        })

    parent = Parent.query.filter_by(user_id=user_id).first()
    if parent:
        # ... (szülő szerepkör adatai)
        roles.append({
            'name': 'Szülő',
            'details': {
                'children': children
            }
        })

    leader = Leader.query.filter_by(user_id=user_id).first()
    if leader:
        club_sports = ClubSport.query.filter_by(club_id=leader.club_id).all()
        sports = [cs.sport.name for cs in club_sports]  # Sportágak neveinek lekérdezése
        roles.append({
            'name': 'Egyesületvezető',
            'details': {
                'club': leader.club.short_name if leader.club else None,
                'sports': sports
            },
            'leader': leader
        })

    return roles

@bp.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Jelszó hash-elése (byte-okat ad vissza)
        hashed_password = bcrypt.generate_password_hash(form.password.data)  # NE dekódold!

        # Új felhasználó létrehozása
        new_user = User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            birth_year=form.birth_year.data,
            email=form.email.data,
            gender=form.gender.data,
            password_hash=hashed_password  # Tárold a byte-okat közvetlenül
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Sikeres regisztráció! Jelentkezz be', 'success')
        return redirect(url_for('routes.login'))
    return render_template('register.html', form=form)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):  # Használd a check_password_hash metódust
            login_user(user)
            return redirect(url_for('routes.dashboard'))
        else:
            flash('Hibás e-mail cím vagy jelszó.')
    return render_template('login.html', title='Bejelentkezés', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('routes.index'))  # Átirányítás a főoldalra

@bp.route('/dashboard')
@login_required
def dashboard():
    # Sportolók lekérdezése (változatlan)
    athletes = Athlete.query.all()

    # Szülők lekérdezése (változatlan)
    parents = Parent.query.all()

    # Edzők lekérdezése a bejelentkezett felhasználó alapján (változatlan)
    coach = Coach.query.filter_by(user_id=current_user.id).first()

    # Vezetők lekérdezése (változatlan)
    leaders = Leader.query.filter_by(user_id=current_user.id).join(Club, Leader.club_id == Club.id).all()

    # Edzőhöz tartozó egyesületek és sportágak lekérdezése
    club_sports = []
    if coach:
        club_sports = ClubSport.query.filter(ClubSport.id.in_([c.club_sport_id for c in Coach.query.filter_by(user_id=coach.user_id).all()])).all()


    return render_template('login/dashboard.html', user=current_user, athletes=athletes,
                                             parents=parents, coach=coach, club_sports=club_sports, leaders=leaders)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required  # Csak bejelentkezett felhasználók számára
def profile():
    user = current_user  # Aktuális felhasználó
    form = ProfileForm(obj=user)  # Űrlap előre töltése a felhasználó adataival
    if form.validate_on_submit():
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.birth_year = form.birth_year.data
        user.email = form.email.data
        user.gender = form.gender.data
        db.session.commit()
        flash('A profil adatok sikeresen frissítve!', 'success')
        return redirect(url_for('routes.profile'))
    return render_template('login/profile.html', form=form)

@bp.route('/create_club', methods=['GET', 'POST'])
@login_required
def create_club():
    form = CreateClubForm()
    if form.validate_on_submit():
        full_name = form.full_name.data
        short_name = form.short_name.data

        existing_club = Club.query.filter_by(short_name=short_name).first()
        if existing_club:
            flash('Az egyesület rövid neve már foglalt!', 'danger')
            return render_template('login/create_club.html', form=form)

        try:
            new_club = Club(full_name=full_name, short_name=short_name, created_by_user_id=current_user.id)
            db.session.add(new_club)
            db.session.commit()
            flash('Új klub sikeresen létrehozva!', 'success')
            return redirect(url_for('routes.create_role_leader'))
        except IntegrityError:
            db.session.rollback()
            flash('Hiba történt a klub létrehozása során. Kérjük, próbálja újra!', 'danger')
    return render_template('login/create_club.html', form=form)

@bp.route('/create_role_leader', methods=['GET', 'POST'])
@login_required
def create_role_leader():
    if check_age(current_user):
        return redirect(url_for('routes.dashboard'))
    form = CreateRoleLeaderForm()
    if form.validate_on_submit():
        leader = Leader(
            user_id=current_user.id,
            club_id=form.club_id.data
        )
        db.session.add(leader)
        try:
            db.session.commit()  # Először mentjük a leadert
            if 'sports' in request.form:  # Ellenőrizzük, hogy vannak-e kiválasztott sportágak
                for sport_id in request.form.getlist('sports'):  # request.form.getlist('sports') lekéri az összes kiválasztott sportágat
                    club_sport = ClubSport(club_id=leader.club_id, sport_id=sport_id)
                    db.session.add(club_sport)
                db.session.commit()
            flash('Egyesületvezetői profil sikeresen létrehozva!', 'success')
            return redirect(url_for('routes.dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Már létezik egyesületvezetői profil ehhez a felhasználóhoz!', 'danger')
    return render_template('login/create_role_leader.html', form=form)

@bp.route('/get_sports/<int:club_id>')
def get_sports(club_id):
    print(f"get_sports útvonal meghívva club_id: {club_id}")
    sports = Sport.query.all()
    sports_list = []
    print(f"Lekérdezett sportágak: {sports}")

    if club_id != 0:
        club = Club.query.get_or_404(club_id)
        selected_sports = [sport.id for sport in club.sports] # Lekérjük a kiválasztott sportágak ID-it

        for sport in sports:
            is_selected = sport.id in selected_sports # Ellenőrzés, hogy a sportág ki van-e választva
            sports_list.append({
                'id': sport.id,
                'name': sport.name,
                'is_selected': is_selected # Hozzáadjuk az is_selected flag-et
            })
    else:
        for sport in sports:
            sports_list.append({
                'id': sport.id,
                'name': sport.name,
                'is_selected': False # Alapértelmezettként nincs kiválasztva
            })

    return jsonify({'sports': sports_list})
   

@bp.route('/create_role_coach', methods=['GET', 'POST'])
@login_required
def create_role_coach():
    if check_age(current_user):
        return redirect(url_for('routes.dashboard'))
    form = CreateRoleCoachForm()
    if form.validate_on_submit():
        club_sport = ClubSport.query.get(form.club_sport_id.data)  # Lekérjük a ClubSport objektumot
        if club_sport:
            coach = Coach(
                user_id=current_user.id,
                club_sport_id=club_sport.id
            )
            db.session.add(coach)
            try:
                db.session.commit()
                flash('Edzői profil sikeresen létrehozva!', 'success')
                return redirect(url_for('routes.dashboard'))
            except Exception as e:
                db.session.rollback()
                print(e)
                flash('Hiba történt az edzői profil létrehozásakor!', 'danger')
        else:
            flash('A kiválasztott egyesület és sportág kombináció nem található!', 'danger')
    return render_template('login/create_role_coach.html', form=form)

@bp.route('/create_role_parent', methods=['GET', 'POST'])
@login_required
def create_role_parent():
    if check_age(current_user):
        return redirect(url_for('routes.dashboard'))
    form = CreateRoleParentForm()
    if form.validate_on_submit():
        parent = Parent(
            user_id=current_user.id,
            coach_id=form.coach_id.data
        )
        db.session.add(parent)
        try:
            db.session.commit()
            flash('Szülői profil sikeresen létrehozva!', 'success')
            return redirect(url_for('routes.dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Már létezik szülői profil ehhez a felhasználóhoz!', 'danger')
    return render_template('login/create_role_parent.html', form=form)

@bp.route('/create_role_athlete', methods=['GET', 'POST'])
@login_required
def create_role_athlete():
    form = CreateRoleAthleteForm()
    if form.validate_on_submit():
        parent = Athlete(
            user_id=current_user.id,
            coach_id=form.coach_id.data
        )
        db.session.add(parent)
        try:
            db.session.commit()
            flash('Sportoló profil sikeresen létrehozva!', 'success')
            return redirect(url_for('routes.dashboard'))
        except IntegrityError:
            db.session.rollback()
            flash('Már létezik sportoló profil ehhez a felhasználóhoz!', 'danger')
    return render_template('login/create_role_athlete.html', form=form)

@bp.route('/add_parents', methods=['GET', 'POST'])
@login_required
def add_parents():
    athlete = Athlete.query.filter_by(user_id=current_user.id).first()

    if not athlete:
        flash('Csak sportolók adhatnak hozzá szülőt!', 'danger')
        return redirect(url_for('routes.dashboard'))

    # Ellenőrizzük az életkort
    age = relativedelta(date.today(), athlete.user.birth_year).years
    if age >= 18:
        flash('Csak 18 év alatti sportolókhoz lehet szülőt rendelni!', 'danger')
        return redirect(url_for('routes.dashboard'))

    # Itt adjuk át az athlete_id-t a formnak!
    form = AddParentsForm(athlete_id=athlete.id)

    if form.validate_on_submit():
        parent_id = form.parent.data

        # Ellenőrizzük, hogy már van-e hozzárendelt szülő
        existing_relationship = AthleteParent.query.filter_by(athlete_id=athlete.id).first()
        if existing_relationship:
            flash('Már van hozzárendelt szülőd!', 'warning')
        else:
            new_parent_link = AthleteParent(athlete_id=athlete.id, parent_id=parent_id)
            db.session.add(new_parent_link)
            db.session.commit()
            flash('Szülő sikeresen hozzárendelve!', 'success')

        return redirect(url_for('routes.dashboard'))

    return render_template('login/add_parents.html', form=form)

@bp.route('/upgrade_leader', methods=['GET', 'POST'])
@login_required
def upgrade_leader():
    leader = Leader.query.filter_by(user_id=current_user.id).first()
    if not leader:
        flash("Nem vagy egyesületvezető!", "danger")
        return redirect(url_for('routes.dashboard'))

    club = Club.query.get_or_404(leader.club_id)
    form = UpgradeClubForm(club)

    if form.validate_on_submit():
        club.full_name = form.full_name.data
        club.short_name = form.short_name.data

        try:
            db.session.commit()
            flash("Egyesület adatai frissítve!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Hiba történt a mentés során: {e}", "danger")
            print(f"Hiba történt a mentés során: {e}")
        return redirect(url_for('routes.dashboard'))

    return render_template('login/upgrade_leader.html', form=form)
