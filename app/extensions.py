from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])

login_manager.login_view = "auth.login"
login_manager.login_message = "Ju lutem kyçuni për të vazhduar."
login_manager.login_message_category = "info"
login_manager.session_protection = "strong"