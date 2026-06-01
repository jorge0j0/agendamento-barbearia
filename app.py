from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from datetime import datetime, date, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "barbearia-corte-arte-secret-2024")

# ── Banco de dados ─────────────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///barbearia.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ── Google OAuth ───────────────────────────────────────────────
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", "SEU_CLIENT_ID_AQUI"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "SEU_CLIENT_SECRET_AQUI"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ══════════════════════════════════════════════════════════════
#  MODELOS
# ══════════════════════════════════════════════════════════════

class Usuario(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(120), nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash  = db.Column(db.String(255))          # None se entrou pelo Google
    google_id   = db.Column(db.String(120))
    foto        = db.Column(db.String(255))
    papel       = db.Column(db.String(20), default="cliente")   # "cliente" ou "admin"
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)
    agendamentos = db.relationship("Agendamento", backref="cliente", lazy=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def checar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


class Agendamento(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    usuario_id  = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    servico     = db.Column(db.String(80), nullable=False)
    preco       = db.Column(db.Float, nullable=False)
    data        = db.Column(db.Date, nullable=False)
    horario     = db.Column(db.String(10), nullable=False)
    status      = db.Column(db.String(20), default="confirmado")  # confirmado / cancelado
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":       self.id,
            "servico":  self.servico,
            "preco":    self.preco,
            "data":     self.data.strftime("%d/%m/%Y"),
            "horario":  self.horario,
            "status":   self.status,
            "cliente":  self.cliente.nome,
            "email":    self.cliente.email,
        }


# ══════════════════════════════════════════════════════════════
#  DECORATORS (proteção de rotas)
# ══════════════════════════════════════════════════════════════

def login_obrigatorio(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_obrigatorio(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        u = db.session.get(Usuario, session["usuario_id"])
        if not u or u.papel != "admin":
            return redirect(url_for("dashboard_cliente"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════
#  ROTAS DE AUTENTICAÇÃO
# ══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if "usuario_id" in session:
        u = db.session.get(Usuario, session["usuario_id"])
        if u and u.papel == "admin":
            return redirect(url_for("dashboard_admin"))
        return redirect(url_for("dashboard_cliente"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        u = Usuario.query.filter_by(email=email).first()
        if u and u.senha_hash and u.checar_senha(senha):
            session["usuario_id"] = u.id
            return redirect(url_for("index"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome  = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        if Usuario.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "erro")
            return render_template("cadastro.html")
        u = Usuario(nome=nome, email=email)
        u.set_senha(senha)
        db.session.add(u)
        db.session.commit()
        session["usuario_id"] = u.id
        return redirect(url_for("dashboard_cliente"))
    return render_template("cadastro.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Google OAuth ───────────────────────────────────────────────

@app.route("/login/google")
def login_google():
    redirect_uri = url_for("callback_google", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def callback_google():
    token = google.authorize_access_token()
    info  = token.get("userinfo")
    if not info:
        flash("Falha ao autenticar com o Google.", "erro")
        return redirect(url_for("login"))

    u = Usuario.query.filter_by(email=info["email"]).first()
    if not u:
        u = Usuario(
            nome=info.get("name", "Usuário"),
            email=info["email"],
            google_id=info["sub"],
            foto=info.get("picture"),
        )
        db.session.add(u)
        db.session.commit()
    else:
        # Atualiza dados do Google se necessário
        u.google_id = info["sub"]
        u.foto = info.get("picture", u.foto)
        db.session.commit()

    session["usuario_id"] = u.id
    return redirect(url_for("index"))


# ══════════════════════════════════════════════════════════════
#  DASHBOARD CLIENTE
# ══════════════════════════════════════════════════════════════

# Gera horários de 08:00 até 20:00 de 30 em 30 minutos (segunda a domingo)
HORARIOS_DISPONIVEIS = []
for h in range(8, 20):
    HORARIOS_DISPONIVEIS.append(f"{h:02d}:00")
    HORARIOS_DISPONIVEIS.append(f"{h:02d}:30")
HORARIOS_DISPONIVEIS.append("20:00")

SERVICOS = [
    {"nome": "Corte Clássico",  "preco": 35, "duracao": "30 min"},
    {"nome": "Barba",           "preco": 25, "duracao": "20 min"},
    {"nome": "Corte + Barba",   "preco": 55, "duracao": "50 min"},
    {"nome": "Hidratação",      "preco": 40, "duracao": "30 min"},
    {"nome": "Coloração",       "preco": 80, "duracao": "60 min"},
    {"nome": "Sobrancelha",     "preco": 15, "duracao": "10 min"},
]


@app.route("/cliente")
@login_obrigatorio
def dashboard_cliente():
    u = db.session.get(Usuario, session["usuario_id"])
    data_hoje = date.today()

    # Data selecionada (padrão = hoje)
    data_str = request.args.get("data", data_hoje.isoformat())
    try:
        data_sel = date.fromisoformat(data_str)
    except ValueError:
        data_sel = data_hoje

    # Horários já ocupados na data selecionada
    ocupados = {
        a.horario for a in Agendamento.query.filter_by(
            data=data_sel, status="confirmado"
        ).all()
    }

    # Próximos 7 dias para escolha (segunda a domingo)
    dias = [data_hoje + timedelta(days=i) for i in range(7)]
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    meus = Agendamento.query.filter_by(
        usuario_id=u.id
    ).order_by(Agendamento.data.desc(), Agendamento.horario).limit(10).all()

    # Marca quais agendamentos podem ser cancelados (falta mais de 24h)
    agora = datetime.now()
    for ag in meus:
        ag_datetime = datetime.combine(ag.data, datetime.strptime(ag.horario, "%H:%M").time())
        ag.pode_cancelar = (ag_datetime - agora) > timedelta(hours=24)

    return render_template(
        "cliente.html",
        usuario=u,
        servicos=SERVICOS,
        horarios=HORARIOS_DISPONIVEIS,
        ocupados=ocupados,
        meus_agendamentos=meus,
        hoje=data_hoje.strftime("%d/%m/%Y"),
        data_sel=data_sel,
        data_sel_str=data_sel.isoformat(),
        dias=dias,
        dias_semana=dias_semana,
    )


@app.route("/cliente/agendar", methods=["POST"])
@login_obrigatorio
def agendar():
    u    = db.session.get(Usuario, session["usuario_id"])
    hora = request.form.get("horario")
    serv = request.form.get("servico")
    data_str = request.form.get("data", date.today().isoformat())
    try:
        data_ag = date.fromisoformat(data_str)
    except ValueError:
        data_ag = date.today()

    preco = next((s["preco"] for s in SERVICOS if s["nome"] == serv), 0)

    # Checa se horário ainda está livre
    conflito = Agendamento.query.filter_by(
        data=data_ag, horario=hora, status="confirmado"
    ).first()
    if conflito:
        flash("Esse horário já foi reservado. Escolha outro.", "erro")
        return redirect(url_for("dashboard_cliente", data=data_str))

    ag = Agendamento(
        usuario_id=u.id,
        servico=serv,
        preco=preco,
        data=data_ag,
        horario=hora,
    )
    db.session.add(ag)
    db.session.commit()
    flash(f"Agendado! {serv} — {data_ag.strftime('%d/%m')} às {hora}.", "ok")
    return redirect(url_for("dashboard_cliente"))


@app.route("/cliente/cancelar/<int:ag_id>", methods=["POST"])
@login_obrigatorio
def cancelar_cliente(ag_id):
    u  = db.session.get(Usuario, session["usuario_id"])
    ag = Agendamento.query.filter_by(id=ag_id, usuario_id=u.id).first_or_404()

    # Regra: só pode cancelar se faltar mais de 24h
    ag_datetime = datetime.combine(ag.data, datetime.strptime(ag.horario, "%H:%M").time())
    if (ag_datetime - datetime.now()) <= timedelta(hours=24):
        flash("Cancelamento não permitido — faltam menos de 24h para o seu horário.", "erro")
        return redirect(url_for("dashboard_cliente"))

    ag.status = "cancelado"
    db.session.commit()
    flash("Agendamento cancelado com sucesso.", "ok")
    return redirect(url_for("dashboard_cliente"))


@app.route("/cliente/apagar/<int:ag_id>", methods=["POST"])
@login_obrigatorio
def apagar_historico(ag_id):
    """Cliente apaga do histórico apenas agendamentos cancelados ou passados."""
    u  = db.session.get(Usuario, session["usuario_id"])
    ag = Agendamento.query.filter_by(id=ag_id, usuario_id=u.id).first_or_404()
    # Só permite apagar se estiver cancelado OU se a data já passou
    if ag.status == "cancelado" or ag.data < date.today():
        db.session.delete(ag)
        db.session.commit()
    return redirect(url_for("dashboard_cliente"))


@app.route("/cliente/apagar-cancelados", methods=["POST"])
@login_obrigatorio
def apagar_todos_cancelados():
    """Apaga todos os cancelados e passados do histórico do cliente de uma vez."""
    u = db.session.get(Usuario, session["usuario_id"])
    Agendamento.query.filter(
        Agendamento.usuario_id == u.id,
        Agendamento.status == "cancelado"
    ).delete()
    # Também apaga agendamentos passados (data anterior a hoje)
    Agendamento.query.filter(
        Agendamento.usuario_id == u.id,
        Agendamento.data < date.today()
    ).delete()
    db.session.commit()
    flash("Histórico limpo com sucesso.", "ok")
    return redirect(url_for("dashboard_cliente"))


# ══════════════════════════════════════════════════════════════
#  DASHBOARD ADMIN
# ══════════════════════════════════════════════════════════════

@app.route("/admin")
@admin_obrigatorio
def dashboard_admin():
    u         = db.session.get(Usuario, session["usuario_id"])
    data_hoje = date.today()
    todos     = Agendamento.query.filter_by(data=data_hoje).order_by(Agendamento.horario).all()
    confirmados = [a for a in todos if a.status == "confirmado"]
    faturamento = sum(a.preco for a in confirmados)
    clientes_total = Usuario.query.filter_by(papel="cliente").count()
    return render_template(
        "admin.html",
        usuario=u,
        agendamentos=todos,
        confirmados=len(confirmados),
        faturamento=faturamento,
        clientes_total=clientes_total,
        hoje=data_hoje.strftime("%d/%m/%Y"),
    )


@app.route("/admin/cancelar/<int:ag_id>", methods=["POST"])
@admin_obrigatorio
def cancelar_admin(ag_id):
    ag = db.session.get(Agendamento, ag_id)
    ag.status = "cancelado"
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/restaurar/<int:ag_id>", methods=["POST"])
@admin_obrigatorio
def restaurar_admin(ag_id):
    ag = db.session.get(Agendamento, ag_id)
    ag.status = "confirmado"
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/excluir/<int:ag_id>", methods=["POST"])
@admin_obrigatorio
def excluir_admin(ag_id):
    ag = db.session.get(Agendamento, ag_id)
    db.session.delete(ag)
    db.session.commit()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════
#  INICIALIZAÇÃO
# ══════════════════════════════════════════════════════════════

def criar_admin():
    """Cria um admin padrão se não existir nenhum."""
    if not Usuario.query.filter_by(papel="admin").first():
        admin = Usuario(nome="Administrador", email="admin@barbearia.com", papel="admin")
        admin.set_senha("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Admin criado: admin@barbearia.com / admin123")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        criar_admin()
    app.run(debug=True)
