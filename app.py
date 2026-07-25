import os
from datetime import datetime, timezone

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Render coloca la aplicación detrás de un proxy.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1
)

database_url = os.environ.get("DATABASE_URL")

if not database_url:
    raise RuntimeError("No se encontró DATABASE_URL")

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Visita(db.Model):
    __tablename__ = "visitas"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(100), nullable=False)
    fecha = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    ruta = db.Column(db.String(300), nullable=False)
    navegador = db.Column(db.Text)


def registrar_visita():
    visita = Visita(
        ip=request.remote_addr or "Desconocida",
        ruta=request.path,
        navegador=request.headers.get(
            "User-Agent",
            "Desconocido"
        )
    )

    db.session.add(visita)
    db.session.commit()


@app.route("/")
def inicio():
    try:
        registrar_visita()
    except Exception as error:
        db.session.rollback()
        app.logger.error(
            "Error guardando visita: %s",
            error
        )

    return render_template("index.html")


@app.route("/admin/visitas")
def visitas():
    registros = Visita.query.order_by(
        Visita.fecha.desc()
    ).limit(200).all()

    return render_template(
        "visitas.html",
        visitas=registros
    )


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )