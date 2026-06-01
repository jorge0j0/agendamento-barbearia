# Corte & Arte — Sistema de Agendamento
Barbearia com login, Google OAuth e painel admin em Python + Flask.

---

## 1. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 2. Configurar o Google OAuth (login com Google)

### Passo a passo:

1. Acesse https://console.cloud.google.com
2. Crie um projeto (ex: "Barbearia")
3. Vá em **APIs e Serviços → Credenciais**
4. Clique em **Criar credenciais → ID do cliente OAuth**
5. Tipo: **Aplicativo da Web**
6. Em "URIs de redirecionamento autorizados", adicione:
   ```
   http://localhost:5000/login/google/callback
   ```
7. Copie o **Client ID** e o **Client Secret**

### Definir as variáveis de ambiente:

**Windows (PowerShell):**
```powershell
$env:GOOGLE_CLIENT_ID="seu_client_id_aqui"
$env:GOOGLE_CLIENT_SECRET="seu_client_secret_aqui"
$env:SECRET_KEY="qualquer-string-secreta"
```

**Mac/Linux:**
```bash
export GOOGLE_CLIENT_ID="seu_client_id_aqui"
export GOOGLE_CLIENT_SECRET="seu_client_secret_aqui"
export SECRET_KEY="qualquer-string-secreta"
```

---

## 3. Rodar o projeto

```bash
python app.py
```

Acesse: http://localhost:5000

---

## 4. Login padrão do Admin

```
E-mail: admin@barbearia.com
Senha:  admin123
```

> Troque a senha após o primeiro acesso!

---

## 5. Estrutura do projeto

```
barbearia/
├── app.py                  # Servidor Flask principal
├── requirements.txt        # Dependências
├── barbearia.db            # Banco de dados SQLite (criado automaticamente)
└── templates/
    ├── base.html           # Layout base (dark mode)
    ├── login.html          # Tela de login + Google
    ├── cadastro.html       # Tela de cadastro
    ├── cliente.html        # Dashboard do cliente
    └── admin.html          # Painel do administrador
```

---

## 6. Funcionalidades

### Cliente:
- Cadastro e login com e-mail/senha
- Login com conta Google (OAuth 2.0)
- Escolher serviço e horário disponível
- Ver e cancelar seus agendamentos

### Administrador:
- Ver todos os agendamentos do dia
- Estatísticas: total, confirmados, faturamento
- Cancelar, restaurar ou excluir agendamentos
- Ver quantidade de clientes cadastrados

---

## 7. Como tornar alguém admin

No terminal Python:
```python
from app import app, db, Usuario
with app.app_context():
    u = Usuario.query.filter_by(email="email@exemplo.com").first()
    u.papel = "admin"
    db.session.commit()
```
