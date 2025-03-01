from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
from flask_login import LoginManager
from flask_bcrypt import Bcrypt  # Importáld a Bcrypt-et

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()  # Inicializáld a Bcrypt-et

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['SQLALCHEMY_ECHO'] = False
    app.config['SQLALCHEMY_FUTURE'] = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)  # Inicializáld a Bcrypt-et is

    # Bejelentkezési nézet beállítása
    login_manager.login_view = 'routes.login'  # 'routes.login' a bejelentkezési route neve

    # Felhasználó betöltése
    from .models import User  # Importáld a User modellt
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Kéknyomok (blueprints) regisztrálása
    from app.routes import bp as routes_bp
    app.register_blueprint(routes_bp, url_prefix='/')

    # Fontos a körkörös importok elkerülése miatt!
    from app import tables, forms  # Először az 'app' modulból importálj!
    from .models import User # Utána a 'models'-ből

    return app