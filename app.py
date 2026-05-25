from flask import Flask, render_template, request, redirect

app = Flask(__name__)

USUARIO = "MANUEL CUBILLOS"
CLAVE = "123456789"

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        clave = request.form["clave"]
        celular = request.form["celular"]

with open("accesos.txt", "a", encoding="utf-8") as archivo:
    archivo.write(f"Usuario: {usuario} | Celular: {celular}\n")

        if usuario == USUARIO and clave == CLAVE:
            return render_template("index.html")

        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

app.run(host="0.0.0.0", port=5000)