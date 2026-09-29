# VexyloSchedule — Plataforma de Gestão de Agendamentos e Serviços

**VexyloSchedule** é uma aplicação web moderna e robusta para agendamento e marcação de serviços em tempo real, desenvolvida especificamente para barbearias, salões de beleza, clínicas e prestadores de serviços.

O sistema dispõe de uma área pública responsiva para clientes com seleção inteligente de horários, área autenticada do cliente com gestão de marcações e histórico fidedigno, e um painel administrativo com visão em calendário interativo (FullCalendar) e métricas analíticas em tempo real.

---

## 🚀 Stack Tecnológica

- **Backend:** Python 3.11+ / Django 5.2 LTS
- **Base de Dados:** PostgreSQL (compatível com Neon Serverless, RDS ou PostgreSQL local)
- **Autenticação:** Django Auth & `django-allauth` (Google OAuth 2.0 com suporte opcional)
- **Painel Administrativo:** Django Admin com tema personalizado Jazzmin
- **Servidor & Ficheiros Estáticos:** Gunicorn & WhiteNoise (com compressão e manifest estático)
- **Frontend:** Django Templates, Vanilla JavaScript, Tailwind CSS e bibliotecas consolidadas (FullCalendar, Chart.js, Flatpickr)
- **Contentorização:** Docker (com utilizador não-root e healthcheck)

---

## 🔒 Princípios de Segurança e Boas Práticas

1. **Agendamento Autoritativo no Servidor:** O frontend é apenas um facilitador de UX. A disponibilidade, horários de funcionamento, intervalos de almoço e atribuição de profissionais são 100% validados no servidor através do `BookingService`.
2. **Proteção Contra Concorrência (Double-Booking):** As operações de agendamento correm sob transações atómicas (`transaction.atomic`) com bloqueio ao nível da linha (`select_for_update`) dos profissionais envolvidos, impedindo marcações concorrentes no mesmo intervalo de tempo.
3. **Prevenção de Stored XSS:** No calendário de administração, os dados de clientes e serviços são construídos estritamente através da API DOM nativa (`document.createElement` e `textContent`), sem recurso a injeção em template strings ou HTML arbitrário.
4. **Sem Credenciais Hardcoded:** Não existem utilizadores pré-configurados com passwords previsíveis (`admin / admin`). A criação do superuser inicial exige variáveis de ambiente explícitas e palavras-passe com requisitos mínimos de segurança.
5. **Mitigação de Host Header Poisoning:** Links de recuperação de palavra-passe são gerados utilizando hosts canónicos e de confiança configurados no servidor (`CANONICAL_HOST` ou `ALLOWED_HOSTS` estritos), eliminando o risco de envenenamento de cabeçalho `Host`.
6. **Integridade Histórica:** Serviços e categorias possuem proteção contra eliminação em cascata (`on_delete=models.PROTECT`). Marcações contêm snapshots imutáveis (`price_at_booking`, `service_name_at_booking`, `duration_at_booking`), garantindo que alterações de preçário no futuro não deturpam o histórico financeiro passado.
7. **Moderação de Avaliações:** Testemunhos submetidos por clientes entram por defeito em estado oculto (`is_visible=False`), exigindo moderação e aprovação prévia antes de serem publicados.
8. **Rate Limiting:** Endpoints sensíveis (registo, agendamento, cancelamento e testemunhos) encontram-se protegidos por limites de frequência de pedidos por IP/utilizador.

---

## ⚙️ Variáveis de Ambiente

Crie um ficheiro `.env` na raiz do projeto com base no modelo fornecido em `.env.example`:

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `DEBUG` | Modo de depuração (deve ser `False` em produção) | `False` |
| `SECRET_KEY` | Chave criptográfica única e aleatória do Django | *(gerar chave forte de 50+ carateres)* |
| `DATABASE_URL` | URL de ligação PostgreSQL (Neon / RDS) | `postgresql://user:pass@host:5432/db?sslmode=require` |
| `ALLOWED_HOSTS` | Domínios autorizados separados por vírgula (sem `*`) | `meusalao.com,www.meusalao.com,.onrender.com` |
| `CANONICAL_HOST` | Domínio canónico para emails de recuperação | `meusalao.com` |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para proteção CSRF em HTTPS | `https://meusalao.com,https://*.onrender.com` |
| `CREATE_INITIAL_SUPERUSER` | Ativa a criação do admin inicial via `seed_data` | `false` ou `true` |
| `INITIAL_SUPERUSER_USERNAME` | Nome de utilizador do superuser inicial | `admin_gestor` |
| `INITIAL_SUPERUSER_EMAIL` | Email do superuser inicial | `admin@meusalao.com` |
| `INITIAL_SUPERUSER_PASSWORD` | Password forte (mínimo 8 carateres, nunca "admin") | `MinhaPassForte2026!` |
| `GOOGLE_CLIENT_ID` | Client ID do Google Cloud Console para OAuth | `123456...apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Client Secret do Google Cloud Console | `GOCSPX-...` |
| `EMAIL_HOST` | Servidor SMTP para envio de emails transacionais | `smtp.gmail.com` |
| `EMAIL_PORT` | Porta do servidor SMTP | `587` ou `465` |
| `EMAIL_HOST_USER` | Utilizador / Email remetente SMTP | `suporte@meusalao.com` |
| `EMAIL_HOST_PASSWORD` | Password de aplicação do email | `xxxx xxxx xxxx xxxx` |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | Encriptação de transporte de email | `True` / `False` |

---

## 🛠️ Instalação e Execução Local

### 1. Clonar e Criar Ambiente Virtual

```bash
git clone <url-do-repositorio>
cd VexyloSchedule
python -m venv venv
# No Windows PowerShell:
.\venv\Scripts\Activate.ps1
# No Linux/macOS:
source venv/bin/activate
```

### 2. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente

Copie o ficheiro `.env.example` para `.env` e ajuste as variáveis necessárias:
```bash
cp .env.example .env
```

### 4. Executar Migrações e Inicializar Dados

```bash
python manage.py migrate
python manage.py seed_data
```

*(O comando `seed_data` é idempotente e cria os horários e serviços base sem sobrescrever dados existentes).*

### 5. Criar Conta de Administrador Manualmente

```bash
python manage.py createsuperuser
```

### 6. Iniciar o Servidor de Desenvolvimento

```bash
python manage.py runserver 8000
```
Aceda ao site em `http://127.0.0.1:8000/` e à área de gestão em `http://127.0.0.1:8000/vexylo-admin/`.

---

## 🧪 Execução de Testes Automatizados

A aplicação dispõe de uma suite abrangente de testes unitários e de integração que cobrem:
- Autenticação e unicidade case-insensitive de emails;
- Mitigação de envenenamento de cabeçalho Host no reset de password;
- Validação estrita de horários de funcionamento, almoço e antecedentes;
- Integridade de slots e prevenção de double-booking concorrente;
- Máquina de estados e permissões de cancelamento;
- Invariantes de modelos, snapshots de preços e proteção contra eliminação;
- Moderação de testemunhos e prevenção de Stored XSS.

Para correr a suite completa:

```bash
python manage.py test
```

Para verificar o estado das migrações e conformidade de segurança para deploy:

```bash
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
```

---

## 🐳 Execução via Docker

O contentor Docker foi configurado para não executar como utilizador `root`, garantindo higiene de segurança através de um utilizador de sistema dedicado (`appuser`):

```bash
# Construir a imagem
docker build -t vexyloschedule:latest .

# Executar o contentor
docker run -d --name vexylo -p 8000:8000 --env-file .env vexyloschedule:latest
```

---

## ⏰ Tarefas Agendadas (Cron / Tarefas em Segundo Plano)

Para processar ou arquivar marcações antigas que já tenham decorrido, o comando de gestão pode ser executado de forma controlada através de um serviço de cron externo (ex: Render Cron Job ou crontab do Linux):

```bash
# Simulação sem alteração (dry-run):
python manage.py close_past_appointments --dry-run

# Execução explícita (diária às 23:00):
python manage.py close_past_appointments --target-status=Concluída
```

*Nota: Ao contrário de versões preliminares, o encerramento automático não é executado de forma cega durante pedidos HTTP GET nem no arranque do contentor, preservando a fidelidade dos registos de negócio.*
