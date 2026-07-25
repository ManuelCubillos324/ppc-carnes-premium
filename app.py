import ipaddress
import os
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy


# =========================================================
# CONFIGURACIÓN DE FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# =========================================================

database_url = os.environ.get(
    "DATABASE_URL",
    "sqlite:///mercado_ganadero.db"
)

# Compatibilidad con enlaces antiguos de PostgreSQL.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# TABLA DE VISITAS
# =========================================================

class Visita(db.Model):
    __tablename__ = "visitas_publicas"

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
        db.String(80),
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
        default="/"
    )

    fecha = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# =========================================================
# VALIDACIÓN DE LA IP
# =========================================================

def limpiar_ip(valor):
    if not isinstance(valor, str):
        return None

    valor = valor.strip()

    if not valor:
        return None

    # IPv6 con corchetes, por ejemplo: [2001:db8::1]
    if valor.startswith("[") and "]" in valor:
        valor = valor[1:valor.index("]")]

    # IPv4 acompañada de puerto, por ejemplo: 181.50.10.20:443
    if valor.count(":") == 1:
        posible_ip, posible_puerto = valor.rsplit(":", 1)

        if posible_puerto.isdigit():
            valor = posible_ip

    return valor.strip()


def ip_es_publica(valor):
    valor = limpiar_ip(valor)

    if not valor:
        return False

    try:
        direccion = ipaddress.ip_address(valor)
        return direccion.is_global

    except ValueError:
        return False


# =========================================================
# GEOLOCALIZACIÓN APROXIMADA
# =========================================================

def consultar_ubicacion(ip):
    resultado = {
        "pais": "Desconocido",
        "region": "Desconocida",
        "ciudad": "Desconocida",
        "proveedor": "Desconocido"
    }

    if not ip_es_publica(ip):
        return resultado

    try:
        respuesta = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=5
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        if datos.get("error"):
            return resultado

        resultado["pais"] = (
            datos.get("country_name")
            or "Desconocido"
        )

        resultado["region"] = (
            datos.get("region")
            or "Desconocida"
        )

        resultado["ciudad"] = (
            datos.get("city")
            or "Desconocida"
        )

        resultado["proveedor"] = (
            datos.get("org")
            or "Desconocido"
        )

    except (requests.RequestException, ValueError) as error:
        app.logger.warning(
            "No se pudo consultar la ubicación de %s: %s",
            ip,
            error
        )

    return resultado


# =========================================================
# DETECCIÓN DEL DISPOSITIVO
# =========================================================

def analizar_dispositivo(user_agent):
    texto = (user_agent or "").lower()

    if "iphone" in texto:
        dispositivo = "Celular"
        sistema = "iOS"

    elif "ipad" in texto:
        dispositivo = "Tableta"
        sistema = "iPadOS"

    elif "android" in texto:
        if "mobile" in texto:
            dispositivo = "Celular"
        else:
            dispositivo = "Tableta"

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

    elif "firefox/" in texto:
        navegador = "Mozilla Firefox"

    elif "crios/" in texto:
        navegador = "Google Chrome"

    elif "chrome/" in texto and "edg/" not in texto:
        navegador = "Google Chrome"

    elif "safari/" in texto and "chrome/" not in texto:
        navegador = "Safari"

    else:
        navegador = "Desconocido"

    return dispositivo, sistema, navegador


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/")
def inicio():
    return render_template("index.html")


# =========================================================
# RECIBIR Y GUARDAR LA VISITA
# =========================================================

@app.route("/registrar-visita", methods=["POST"])
def registrar_visita():
    datos = request.get_json(silent=True)

    if not datos:
        return jsonify({
            "ok": False,
            "error": "No se recibieron datos"
        }), 400

    ip = limpiar_ip(datos.get("ip"))
    ruta = datos.get("ruta", "/")

    if not ip_es_publica(ip):
        return jsonify({
            "ok": False,
            "error": "La IP recibida no es pública o no es válida"
        }), 400

    if not isinstance(ruta, str):
        ruta = "/"

    ruta = ruta[:300]

    user_agent = request.headers.get(
        "User-Agent",
        ""
    )

    ubicacion = consultar_ubicacion(ip)

    dispositivo, sistema, navegador = analizar_dispositivo(
        user_agent
    )

    try:
        visita = Visita(
            ip=ip,
            pais=ubicacion["pais"],
            region=ubicacion["region"],
            ciudad=ubicacion["ciudad"],
            proveedor=ubicacion["proveedor"],
            dispositivo=dispositivo,
            sistema=sistema,
            navegador=navegador,
            ruta=ruta
        )

        db.session.add(visita)
        db.session.commit()

        app.logger.info(
            "Visita registrada: %s - %s - %s",
            ip,
            ubicacion["pais"],
            ubicacion["ciudad"]
        )

        return jsonify({
            "ok": True,
            "mensaje": "Visita registrada correctamente"
        })

    except Exception as error:
        db.session.rollback()

        app.logger.exception(
            "No se pudo guardar la visita: %s",
            error
        )

        return jsonify({
            "ok": False,
            "error": "No se pudo guardar la visita"
        }), 500


# =========================================================
# PANEL DE VISITAS
# =========================================================

@app.route("/admin/visitas")
def ver_visitas():
    visitas = Visita.query.order_by(
        Visita.fecha.desc()
    ).limit(200).all()

    return render_template(
        "visitas.html",
        visitas=visitas
    )


# =========================================================
# CREAR TABLAS
# =========================================================

with app.app_context():
    db.create_all()


# =========================================================
# EJECUCIÓN LOCAL
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )