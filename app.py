import ipaddress
import os
import re
from datetime import datetime, timezone

import requests
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)


# =========================================================
# BASE DE DATOS
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
# MODELO DE VISITAS
# =========================================================

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
        nullable=False
    )

    fecha = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# =========================================================
# FUNCIONES PARA LA IP
# =========================================================

def limpiar_ip(valor):
    """
    Limpia una dirección que pueda venir con espacios,
    comillas, corchetes o puerto.
    """

    if not valor:
        return None

    valor = valor.strip().strip('"').strip("'")

    # IPv6 encerrada entre corchetes: [2001:db8::1]:443
    if valor.startswith("[") and "]" in valor:
        valor = valor[1:valor.index("]")]

    # IPv4 con puerto: 181.50.10.20:443
    if valor.count(":") == 1:
        posible_ip, posible_puerto = valor.rsplit(":", 1)

        if posible_puerto.isdigit():
            valor = posible_ip

    return valor.strip()


def ip_es_publica(valor):
    """
    Comprueba si es una IP pública enrutable.
    Rechaza 10.x.x.x, 127.0.0.1, 192.168.x.x
    y otros rangos privados o reservados.
    """

    valor = limpiar_ip(valor)

    if not valor:
        return False

    try:
        direccion = ipaddress.ip_address(valor)
        return direccion.is_global

    except ValueError:
        return False


def obtener_ips_de_forwarded(valor):
    """
    Extrae IPs del encabezado estándar Forwarded.

    Ejemplo:
    for=181.50.20.10;proto=https
    """

    if not valor:
        return []

    coincidencias = re.findall(
        r'for="?(\[[^\]]+\]|[^;,\s"]+)"?',
        valor,
        flags=re.IGNORECASE
    )

    return coincidencias


def obtener_ip_visitante():
    """
    Busca la primera IP pública válida en las cabeceras
    recibidas por Render.
    """

    candidatos = []

    # Cabeceras que algunos proxies o CDN pueden utilizar.
    cabeceras_individuales = [
        "CF-Connecting-IP",
        "True-Client-IP",
        "X-Real-IP"
    ]

    for nombre in cabeceras_individuales:
        valor = request.headers.get(nombre)

        if valor:
            candidatos.append(valor)

    # X-Forwarded-For puede contener varias IP separadas por comas.
    forwarded_for = request.headers.get(
        "X-Forwarded-For",
        ""
    )

    if forwarded_for:
        candidatos.extend(
            parte.strip()
            for parte in forwarded_for.split(",")
            if parte.strip()
        )

    # Encabezado estándar Forwarded.
    forwarded = request.headers.get(
        "Forwarded",
        ""
    )

    candidatos.extend(
        obtener_ips_de_forwarded(forwarded)
    )

    # Última alternativa.
    if request.remote_addr:
        candidatos.append(request.remote_addr)

    # Únicamente se acepta una IP verdaderamente pública.
    for candidato in candidatos:
        ip_limpia = limpiar_ip(candidato)

        if ip_es_publica(ip_limpia):
            return ip_limpia

    return "Desconocida"


# =========================================================
# GEOLOCALIZACIÓN APROXIMADA
# =========================================================

def consultar_ubicacion(ip):
    resultado_vacio = {
        "pais": "Desconocido",
        "region": "Desconocida",
        "ciudad": "Desconocida",
        "proveedor": "Desconocido"
    }

    if not ip_es_publica(ip):
        return resultado_vacio

    try:
        respuesta = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=5
        )

        respuesta.raise_for_status()
        datos = respuesta.json()

        if datos.get("error"):
            return resultado_vacio

        return {
            "pais": datos.get(
                "country_name"
            ) or "Desconocido",

            "region": datos.get(
                "region"
            ) or "Desconocida",

            "ciudad": datos.get(
                "city"
            ) or "Desconocida",

            "proveedor": datos.get(
                "org"
            ) or "Desconocido"
        }

    except (
        requests.RequestException,
        ValueError
    ) as error:

        app.logger.warning(
            "No se pudo consultar la ubicación de %s: %s",
            ip,
            error
        )

        return resultado_vacio