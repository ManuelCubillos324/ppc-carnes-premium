import ipaddress
import os
from datetime import datetime, timezone

import requests
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

# Render coloca la aplicación detrás de un proxy.
# ProxyFix permite interpretar correctamente la IP y el protocolo.
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1
)

database_url = os.environ.get(
    "DATABASE_URL",
    "sqlite:///mercado_ganadero.db"
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class VisitaDetallada(db.Model):
    __tablename__ = "visitas_detalladas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    ip = db.Column(
        db.String(100),
        nullable=False
    )

    pais = db.Column(
        db.String(100),
        default="Desconocido"
    )

    region = db.Column(
        db.String(120),
        default="Desconocida"
    )

    ciudad = db.Column(
        db.String(120),
        default="Desconocida"
    )

    proveedor = db.Column(
        db.String(250),
        default="Desconocido"
    )

    dispositivo = db.Column(
        db.String(50),
        default="Desconocido"
    )

    sistema = db.Column(
        db.String(100),
        default="Desconocido"
    )

    navegador = db.Column(
        db.String(100),
        default="Desconocido"
    )

    ruta = db.Column(
        db.String(300),
        nullable=False
    )

    fecha = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


def obtener_ip_visitante():
    """
    Obtiene la IP pública más cercana disponible.
    ProxyFix permite que remote_addr use la información
    suministrada por el proxy de Render.
    """

    return request.remote_addr or "Desconocida"


def ip_es_publica(ip):
    try:
        direccion = ipaddress.ip_address(ip)

        return not (
            direccion.is_private
            or direccion.is_loopback
            or direccion.is_reserved
            or direccion.is_multicast
        )

    except ValueError:
        return False


def consultar_ubicacion(ip):
    datos_vacios = {
        "pais": "Desconocido",
        "region": "Desconocida",
        "ciudad": "Desconocida",
        "proveedor": "Desconocido"
    }

    if not ip_es_publica(ip):
        return datos_vacios

    try:
        respuesta = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=4
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        if datos.get("error"):
            return datos_vacios

        return {
            "pais": datos.get(
                "country_name",
                "Desconocido"
            ),
            "region": datos.get(
                "region",
                "Desconocida"
            ),
            "ciudad": datos.get(
                "city",
                "Desconocida"
            ),
            "proveedor": datos.get(
                "org",
                "Desconocido"
            )
        }

    except (
        requests.RequestException,
        ValueError
    ) as error:
        app.logger.warning(
            "No se pudo consultar la ubicación: %s",
            error
        )

        return datos_vacios


def analizar_dispositivo(user_agent):
    texto = user_agent.lower()

    if "iphone" in texto or "ipad" in texto:
        dispositivo = "Celular o tableta"
        sistema = "iOS / iPadOS"

    elif "android" in texto:
        dispositivo = "Celular o tableta"
        sistema = "Android"

    elif "windows" in texto:
        dispositivo = "Computador"
        sistema = "Windows"

    elif "macintosh" in texto or "mac os" in texto:
        dispositivo = "Computador"
        sistema = "macOS"

    elif "linux" in texto:
        dispositivo = "Computador"
        sistema = "Linux"

    else:
        dispositivo = "Desconocido"
        sistema = "Desconocido"

    if "edg/" in texto:
        navegador = "Microsoft Edge"

    elif "opr/" in texto or "opera" in texto:
        navegador = "Opera"

    elif "chrome/" in texto and "edg/" not in texto:
        navegador = "Google Chrome"

    elif "firefox/" in texto:
        navegador = "Mozilla Firefox"

    elif "safari/" in texto and "chrome/" not in texto:
        navegador = "Safari"

    else:
        navegador = "Desconocido"

    return dispositivo, sistema, navegador


def registrar_visita():
    user_agent = request.headers.get(
        "User-Agent",
        ""
    )

    # Evita registrar algunos controles automáticos de Render.
    if user_agent.startswith("Go-http-client/"):
        return

    ip = obtener_ip_visitante()
    ubicacion = consultar_ubicacion(ip)

    dispositivo, sistema, navegador = analizar_dispositivo(
        user_agent
    )

    visita = VisitaDetallada(
        ip=ip,
        pais=ubicacion["pais"],
        region=ubicacion["region"],
        ciudad=ubicacion["ciudad"],
        proveedor=ubicacion["proveedor"],
        dispositivo=dispositivo,
        sistema=sistema,
        navegador=navegador,
        ruta=request.path
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
            "No se pudo guardar la visita: %s",
            error
        )

    return render_template("index.html")

print("REMOTE_ADDR:", request.remote_addr)
print("X-Forwarded-For:", request.headers.get("X-Forwarded-For"))
print("X-Real-IP:", request.headers.get("X-Real-IP"))
print("CF-Connecting-IP:", request.headers.get("CF-Connecting-IP"))
@app.route("/admin/visitas")
def ver_visitas():
    visitas = VisitaDetallada.query.order_by(
        VisitaDetallada.fecha.desc()
    ).limit(200).all()

    return render_template(
        "visitas.html",
        visitas=visitas
    )


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )