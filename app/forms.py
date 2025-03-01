from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, DateField, EmailField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo
from .models import GenderEnum, Club, ClubSport, Coach, Parent, Sport, Athlete

class RegistrationForm(FlaskForm):
    first_name = StringField('Keresztnév', validators=[DataRequired()])
    last_name = StringField('Vezetéknév', validators=[DataRequired()])
    birth_year = DateField('Születési dátum', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    gender = SelectField('Nem', choices=[(tag.value, tag.name) for tag in GenderEnum], validators=[DataRequired()])  # SelectField hozzáadva
    password = PasswordField('Jelszó', validators=[DataRequired()])
    confirm_password = PasswordField('Jelszó megerősítése', validators=[DataRequired(), EqualTo('password', message='A jelszavaknak egyezniük kell!')])
    submit = SubmitField('Regisztráció')

class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Jelszó', validators=[DataRequired()])

class ProfileForm(FlaskForm):
    first_name = StringField('Keresztnév', validators=[DataRequired()])
    last_name = StringField('Vezetéknév', validators=[DataRequired()])
    birth_year = DateField('Születési év', validators=[DataRequired()])
    email = EmailField('E-mail cím', validators=[DataRequired(), Email()])
    gender = SelectField('Nem', choices=[('Férfi', 'Férfi'), ('Nő', 'Nő')], validators=[DataRequired()])

class CreateClubForm(FlaskForm):
    full_name = StringField('Klub teljes neve', validators=[DataRequired()])
    short_name = StringField('Klub rövid neve', validators=[DataRequired()])
    submit = SubmitField('Klub létrehozása')

class CreateRoleLeaderForm(FlaskForm):
    club_id = SelectField('Egyesület', choices=[], validators=[DataRequired()])
    submit = SubmitField('Mentés')

    def __init__(self, *args, **kwargs):
        super(CreateRoleLeaderForm, self).__init__(*args, **kwargs)
        clubs = Club.query.all()
        self.club_id.choices = [(club.id, club.full_name) for club in clubs] 

class CreateRoleCoachForm(FlaskForm):
    club_sport_id = SelectField('Egyesület és Sportág', choices=[], validators=[DataRequired()])
    submit = SubmitField('Mentés')

    def __init__(self, *args, **kwargs):
        super(CreateRoleCoachForm, self).__init__(*args, **kwargs)
        club_sports = ClubSport.query.all()
        self.club_sport_id.choices = [(cs.id, f"{cs.club.full_name} - {cs.sport.name}") for cs in club_sports]

class CreateRoleAthleteForm(FlaskForm):
    coach_id = SelectField('Edző', choices=[], validators=[DataRequired()])
    submit = SubmitField('Mentés')

    def __init__(self, *args, **kwargs):
        super(CreateRoleAthleteForm, self).__init__(*args, **kwargs)
        coaches = Coach.query.all()
        self.coach_id.choices = [(coach.id, f"{coach.user.first_name} {coach.user.last_name} ({coach.club_sport.club.full_name} - {coach.club_sport.sport.name})") for coach in coaches]

class CreateRoleParentForm(FlaskForm):
    coach_id = SelectField('Edző', choices=[], validators=[DataRequired()])
    submit = SubmitField('Mentés')

    def __init__(self, *args, **kwargs):
        super(CreateRoleParentForm, self).__init__(*args, **kwargs)
        coaches = Coach.query.all()
        self.coach_id.choices = [(coach.id, f"{coach.user.first_name} {coach.user.last_name} ({coach.club_sport.club.full_name} - {coach.club_sport.sport.name})") for coach in coaches]

class AddParentsForm(FlaskForm):
    parent = SelectField('Szülő', choices=[], coerce=int)
    submit = SubmitField('Mentés')

    def __init__(self, athlete_id, *args, **kwargs):
        super(AddParentsForm, self).__init__(*args, **kwargs)
        athlete = Athlete.query.get(athlete_id)

        if athlete and athlete.coach:
            # Meghatározzuk a klub és sportág kapcsolatot az edző alapján
            club_sport = ClubSport.query.get(athlete.coach.club_sport_id)

            if club_sport:
                self.parent.choices = [
                    (parent.id, f"{parent.user.first_name} {parent.user.last_name}") 
                    for parent in Parent.query.filter_by(
                        coach_id=athlete.coach_id  # Az edzőhöz rendelt szülők szűrése
                    ).all()
                ]

class UpgradeClubForm(FlaskForm):
    full_name = StringField('Teljes név', validators=[DataRequired()])
    short_name = StringField('Rövid név', validators=[DataRequired()])
    submit = SubmitField('Mentés')

    def __init__(self, club, *args, **kwargs):
        super(UpgradeClubForm, self).__init__(*args, **kwargs)
        self.full_name.data = club.full_name
        self.short_name.data = club.short_name