from flask import Blueprint,render_template,request,redirect,url_for,flash
from flask_login import login_user,logout_user,login_required
from flask import session
from . import db
from .models import AuditLog
from .models import User
auth_bp=Blueprint("auth",__name__)
@auth_bp.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(username=request.form.get("username","").strip(),active=True).first()
        if u and u.check_password(request.form.get("password","")):
            session.clear()
            login_user(u, remember=False)
            session.permanent = True
            db.session.add(AuditLog(user_id=u.id, action="CONNEXION", entity="User", entity_id=str(u.id), details="Connexion réussie"))
            db.session.commit()
            return redirect(url_for("main.home"))
        flash("Identifiants incorrects.","danger")
    return render_template("login.html")
@auth_bp.post("/logout")
@login_required
def logout():
    if getattr(__import__("flask_login").current_user, "is_authenticated", False):
        db.session.add(AuditLog(user_id=__import__("flask_login").current_user.id, action="DECONNEXION", entity="User", entity_id=str(__import__("flask_login").current_user.id), details="Déconnexion"))
        db.session.commit()
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
