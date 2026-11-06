import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask import request, flash, redirect, url_for
from flask_login import current_user
import click
import subprocess
import shutil
from pathlib import Path
from sqlalchemy.engine import make_url

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(test_config=None):
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    is_production = os.getenv("FLASK_ENV", "").lower() == "production" or os.getenv("RAILWAY_ENVIRONMENT", "").lower() == "production"
    configured_secret = os.getenv("SECRET_KEY")
    if is_production and (not configured_secret or configured_secret == "dev-only-change-me" or len(configured_secret) < 32):
        raise RuntimeError("SECRET_KEY doit être défini avec au moins 32 caractères aléatoires en production.")

    app.config.update(
        SECRET_KEY=configured_secret or "dev-only-change-me",
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=45),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(Path(app.instance_path) / "uploads")),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"
    csrf.init_app(app)

    from . import models
    from .routes import bp
    from .auth import auth_bp
    app.register_blueprint(bp)
    app.register_blueprint(auth_bp)

    # Contrôle serveur des accès par module : les écrans ne sont pas protégés
    # uniquement par la visibilité des liens de navigation.
    @app.before_request
    def enforce_module_permissions():
        if not current_user.is_authenticated or request.endpoint in {None, "auth.login", "auth.logout", "main.home", "health", "main.patient_portal_login", "main.patient_portal_activate", "main.patient_portal_home", "main.patient_portal_change_request", "main.patient_portal_logout"}:
            return None
        endpoint = request.endpoint
        required = None
        if endpoint.startswith("main.hr_") or endpoint in {"main.payroll_index", "main.payroll_component_new", "main.payroll_new", "main.payroll_slip", "main.payroll_status", "main.staff_card"}: required = "hr.manage"
        elif endpoint.startswith("main.carousel_"): required = "settings.manage"
        elif endpoint.startswith("main.staff_") or endpoint in {"main.roles_admin", "main.permissions_seed"}: required = "staff.manage"
        elif endpoint == "main.audit_admin": required = "audit.view"
        elif endpoint in {"main.patient_appointment_change_requests", "main.patient_appointment_change_decision"}: required = "reception.manage"
        elif endpoint.startswith("main.patient_") or endpoint == "main.patients":
            required = {"main.patient_new":"patients.create", "main.patient_edit":"patients.edit", "main.patient_delete":"patients.archive"}.get(endpoint, "patients.view")
        elif endpoint.startswith("main.admission_") or endpoint in {"main.admissions", "main.admission_new", "main.admission_discharge", "main.ward_create", "main.room_create", "main.bed_create"}: required = "admissions.manage"
        elif endpoint.startswith("main.billing") or endpoint.startswith("main.invoice_") or endpoint.startswith("main.payment_") or endpoint == "main.patient_visit_invoice":
            required = "billing.authorize_coverage" if endpoint == "main.invoice_authorize_coverage" else ("billing.collect" if any(x in endpoint for x in ("payment", "receipt")) else "billing.view")
        elif endpoint.startswith("main.pharmacy"): required = "pharmacy.manage"
        elif endpoint.startswith("main.laboratory") or endpoint.startswith("main.lab_"): required = "laboratory.manage"
        elif endpoint.startswith("main.consultation") or endpoint.startswith("main.prescription"): required = "clinical.write"
        elif endpoint == "main.consultation_available_slots":
            required = "reception.manage"
        elif endpoint.startswith("main.professional_agenda"):
            required = "reception.manage"
        elif endpoint.startswith("main.professional_schedules"):
            required = "hr.manage"
        elif endpoint.startswith("main.reception") or endpoint.startswith("main.appointment") or endpoint.startswith("main.online_appointment") or endpoint.startswith("main.triage") or endpoint == "main.emergency_visit_new": required = "reception.manage"
        elif endpoint == "main.dashboard": required = "dashboard.view"
        if required:
            from .routes import user_has_permission
            if not user_has_permission(current_user, required):
                flash("Votre compte ne possède pas l'autorisation nécessaire pour cette fonction.", "danger")
                return redirect(url_for("main.dashboard"))
        return None

    @app.cli.command("send-appointment-reminders")
    @click.option("--dry-run", is_flag=True, help="Affiche les rappels à envoyer sans contacter les patients.")
    def send_appointment_reminders(dry_run):
        """Envoie les rappels J-1 et H-2. À planifier toutes les 15 minutes."""
        from datetime import datetime, timedelta
        from .models import Appointment, AppointmentNotification, PatientPortalAccount
        from .routes import _send_appointment_email
        now = datetime.now()
        windows = [("J-1", now + timedelta(hours=23, minutes=45), now + timedelta(hours=24, minutes=15)),
                   ("H-2", now + timedelta(hours=1, minutes=45), now + timedelta(hours=2, minutes=15))]
        sent = failed = skipped = 0
        for kind, start, end in windows:
            appointments = Appointment.query.filter(Appointment.status == "PLANIFIE", Appointment.scheduled_at >= start, Appointment.scheduled_at < end).all()
            for appt in appointments:
                existing = AppointmentNotification.query.filter_by(appointment_id=appt.id, reminder_type=kind).first()
                if existing and existing.status == "ENVOYE":
                    skipped += 1; continue
                account = PatientPortalAccount.query.filter_by(patient_id=appt.patient_id, active=True).first()
                recipient = (account.email if account else (appt.patient.email or "")).strip()
                if not recipient:
                    skipped += 1; continue
                if dry_run:
                    click.echo(f"SIMULATION {kind}: {appt.appointment_number} -> {recipient}"); continue
                if not existing:
                    existing = AppointmentNotification(appointment_id=appt.id, reminder_type=kind, recipient=recipient)
                    db.session.add(existing)
                existing.recipient = recipient; existing.attempts += 1; existing.last_error = None
                service = appt.service.name if appt.service else "Consultation"
                body = (f"Bonjour {appt.patient.full_name},\n\nRappel : votre rendez-vous à l’Hôpital La Providence "
                        f"est prévu le {appt.scheduled_at:%d/%m/%Y à %H:%M}.\nService : {service}.\nRéférence : {appt.appointment_number}.\n\n"
                        "En cas d’empêchement, contactez l’accueil. Ce message ne contient aucune information médicale.")
                if _send_appointment_email(recipient, f"Rappel de rendez-vous ({kind}) — Hôpital La Providence", body):
                    existing.status = "ENVOYE"; existing.sent_at = datetime.utcnow(); sent += 1
                else:
                    existing.status = "ECHEC"; existing.last_error = "Échec SMTP ou configuration e-mail indisponible"; failed += 1
                db.session.commit()
        click.echo(f"Rappels envoyés: {sent}; échecs: {failed}; ignorés: {skipped}" + (" (simulation)" if dry_run else ""))

    @app.cli.command("init-access")
    def init_access():
        """Initialise le catalogue des permissions et le rôle super_admin."""
        from .models import Permission, Role
        from .routes import PERMISSION_CATALOG
        for code, description in PERMISSION_CATALOG.items():
            permission = Permission.query.filter_by(code=code).first()
            if permission is None: db.session.add(Permission(code=code, description=description))
        db.session.flush()
        role = Role.query.filter_by(name="super_admin").first()
        if role is None: role = Role(name="super_admin"); db.session.add(role)
        role.permissions = Permission.query.all()
        db.session.commit()
        click.echo("Catalogue initialisé. Rôle super_admin prêt.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--full-name", prompt="Nom complet")
    def create_admin(username, full_name):
        """Crée un compte administrateur initial avec saisie interactive du secret."""
        from werkzeug.security import generate_password_hash
        from .models import User, Role
        if User.query.filter_by(username=username.strip().lower()).first():
            raise click.ClickException("Cet identifiant existe déjà.")
        password = click.prompt("Mot de passe initial (12 caractères minimum)", hide_input=True, confirmation_prompt=True)
        if len(password) < 12: raise click.ClickException("Le mot de passe doit contenir au moins 12 caractères.")
        role = Role.query.filter_by(name="super_admin").first()
        if role is None: raise click.ClickException("Exécutez d'abord : flask init-access")
        user = User(username=username.strip().lower(), full_name=full_name.strip(), active=True)
        user.set_password(password); user.roles = [role]
        db.session.add(user); db.session.commit()
        click.echo("Compte administrateur créé. Conservez les identifiants de manière sécurisée.")

    # Journalise les consultations de dossiers sensibles sans enregistrer de données médicales.
    @app.after_request
    def audit_sensitive_access(response):
        if (current_user.is_authenticated and request.method == "GET" and response.status_code < 400
                and request.endpoint and request.endpoint.startswith("main.")):
            endpoint = request.endpoint
            sensitive_groups = {
                "Patient": ("patient_detail", "patient_edit"),
                "Consultation": ("consultation_", "prescription_"),
                "Admission": ("admission_",),
                "Laboratoire": ("lab_", "laboratory_"),
            }
            entity = next((name for name, prefixes in sensitive_groups.items()
                           if any(endpoint.split(".")[-1].startswith(prefix) for prefix in prefixes)), None)
            if entity:
                try:
                    from .models import AuditLog
                    view_args = request.view_args or {}
                    entity_id = next((str(view_args[k]) for k in ("patient_id", "consultation_id", "admission_id", "order_id", "id") if k in view_args), None)
                    db.session.add(AuditLog(user_id=current_user.id, action="CONSULTATION_DOSSIER",
                                            entity=entity, entity_id=entity_id,
                                            details=f"Consultation de l'écran {endpoint}"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    app.logger.exception("Échec d'enregistrement du journal d'accès sensible")
        return response

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store") if request.endpoint and any(
            token in request.endpoint for token in ("patient", "consultation", "prescription", "admission", "lab", "laboratory")
        ) else None
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.cli.command("backup-db")
    @click.option("--output", required=True, type=click.Path(path_type=Path, dir_okay=False))
    def backup_db(output):
        """Crée une sauvegarde locale de la base (commande réservée à l'administrateur système)."""
        engine_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        output.parent.mkdir(parents=True, exist_ok=True)
        if engine_url.get_backend_name() == "postgresql":
            executable = shutil.which("pg_dump")
            if not executable:
                raise click.ClickException("pg_dump est absent. Installez les outils PostgreSQL sur le serveur de sauvegarde.")
            result = subprocess.run([executable, "--format=custom", "--no-owner", "--file", str(output), app.config["SQLALCHEMY_DATABASE_URI"]], capture_output=True, text=True)
            if result.returncode:
                output.unlink(missing_ok=True)
                raise click.ClickException("Échec de sauvegarde PostgreSQL. Vérifiez les accès et la disponibilité de pg_dump.")
        elif engine_url.get_backend_name() == "sqlite":
            import sqlite3
            database_file = engine_url.database
            if not database_file or database_file == ":memory:":
                raise click.ClickException("La base SQLite en mémoire ne peut pas être sauvegardée.")
            source = Path(database_file)
            if not source.is_absolute(): source = Path(app.instance_path) / source
            if not source.exists(): raise click.ClickException("Fichier SQLite introuvable.")
            with sqlite3.connect(str(source)) as src, sqlite3.connect(str(output)) as dst:
                src.backup(dst)
        else:
            raise click.ClickException("Moteur de base non pris en charge pour la sauvegarde.")
        click.echo(f"Sauvegarde créée : {output} ({output.stat().st_size} octets). Protégez ce fichier : il contient des données confidentielles.")

    @app.cli.command("restore-db")
    @click.option("--input", "input_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
    @click.option("--confirm", is_flag=True, help="Confirme le remplacement des données actuelles.")
    def restore_db(input_file, confirm):
        """Restaure une sauvegarde. Opération destructive, à exécuter hors exploitation."""
        if not confirm:
            raise click.ClickException("Restauration annulée : ajoutez --confirm après avoir arrêté l'application et vérifié la sauvegarde.")
        if click.prompt("Tapez RESTAURER pour remplacer les données actuelles", type=str) != "RESTAURER":
            raise click.ClickException("Confirmation incorrecte. Aucune restauration effectuée.")
        engine_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        if engine_url.get_backend_name() == "postgresql":
            executable = shutil.which("pg_restore")
            if not executable: raise click.ClickException("pg_restore est absent.")
            result = subprocess.run([executable, "--clean", "--if-exists", "--no-owner", "--dbname", app.config["SQLALCHEMY_DATABASE_URI"], str(input_file)], capture_output=True, text=True)
            if result.returncode: raise click.ClickException("Échec de restauration PostgreSQL. Consultez les journaux système sans publier les secrets.")
        elif engine_url.get_backend_name() == "sqlite":
            import sqlite3
            database_file = engine_url.database
            if not database_file or database_file == ":memory:": raise click.ClickException("Cible SQLite non prise en charge.")
            target = Path(database_file)
            if not target.is_absolute(): target = Path(app.instance_path) / target
            target.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(input_file)) as src, sqlite3.connect(str(target)) as dst: src.backup(dst)
        else: raise click.ClickException("Moteur de base non pris en charge.")
        click.echo("Restauration terminée. Vérifiez les données et les journaux avant de remettre le service en ligne.")

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "Hopital La Providence"}, 200

    return app
