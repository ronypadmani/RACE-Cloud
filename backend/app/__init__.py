"""
RACE-Cloud Flask Application Factory
"""
import os
from datetime import timedelta
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

from .database import init_db
from .routes.auth import auth_bp
from .routes.aws_routes import aws_bp
from .routes.analysis import analysis_bp
from .routes.reports import reports_bp
from .routes.iam_guide import iam_guide_bp
from .routes.forecast import forecast_bp
from .routes.dependency import dependency_bp, simulation_bp
from .routes.decision import decision_bp
from .routes.demo import demo_bp


def create_app():
    """Application factory pattern."""
    # Explicitly point to backend/.env so it loads regardless of CWD
    _dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    load_dotenv(dotenv_path=_dotenv_path)

    app = Flask(__name__, instance_relative_config=True)

    # ── Configuration ──────────────────────────────────────────
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-change-me')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-dev-secret-change-me')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(
        hours=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '24'))
    )
    app.config['DATABASE_PATH'] = os.path.join(
        app.instance_path,
        os.getenv('DATABASE_PATH', 'racecloud.db')
    )
    app.config['FERNET_KEY'] = os.getenv('FERNET_ENCRYPTION_KEY', '')

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # ── Extensions ─────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {
        "origins": os.getenv('FRONTEND_URL', 'http://localhost:3000'),
        "supports_credentials": True
    }})
    JWTManager(app)

    # ── Database ───────────────────────────────────────────────
    init_db(app)

    # ── Blueprints ─────────────────────────────────────────────
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(aws_bp, url_prefix='/api/aws')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(iam_guide_bp, url_prefix='/api/iam')
    app.register_blueprint(forecast_bp, url_prefix='/api/forecast')
    app.register_blueprint(dependency_bp, url_prefix='/api/analysis')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(decision_bp, url_prefix='/api/decision')
    app.register_blueprint(demo_bp, url_prefix='/api/demo')

    # ── Health Check ───────────────────────────────────────────
    @app.route('/api/health')
    def health():
        return {'status': 'healthy', 'service': 'RACE-Cloud API'}

    return app
