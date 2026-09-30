# VexyloSchedule — Plataforma de Gestão de Agendamentos e Serviços

**VexyloSchedule** é uma aplicação web moderna e robusta para agendamento e marcação de serviços em tempo real, desenvolvida especificamente para barbearias, salões de beleza, clínicas e prestadores de serviços.

O sistema dispõe de uma área pública responsiva para clientes com seleção inteligente de horários, área autenticada do cliente com gestão de marcações e histórico fidedigno, e um painel administrativo com visão em calendário interativo (FullCalendar) e métricas analíticas em tempo real.

---

## 🚀 Stack Tecnológica

- **Backend:** Python 3.11+ / Django 5.2 LTS
- **Base de Dados:** PostgreSQL (compatível com Neon Serverless, RDS ou PostgreSQL local; SQLite suportado para desenvolvimento e testes rápidos)
- **Autenticação:** Django Auth & `django-allauth` (Google OAuth 2.0 condicional caso as credenciais estejam configuradas)
- **Painel Administrativo:** Django Admin com tema personalizado Jazzmin
- **Servidor & Ficheiros Estáticos:** Gunicorn & WhiteNoise (com armazenamento moderno Django 5.2 `STORAGES`, compressão gzip/brotli e manifest estático)
- **Frontend:** Django Templates, Vanilla JavaScript, Tailwind CSS compilado localmente em build sem Play CDN, FullCalendar 6.1.15, Chart.js 4.4.7 e Flatpickr 4.6.13
- **Cache & Rate Limiting:** `DatabaseCache` partilhado em produção (suportando múltiplos workers Gunicorn) e `LocMemCache` em desenvolvimento
- **Contentorização:** Docker multi-stage (Node.js para compilação CSS, Python wheel builder, imagem final slim sem compiladores, executada sob utilizador não-root `appuser`)

---

## 🔒 Princípios de Segurança e Regras de Negócio

1. **Agendamento Autoritativo com Datetimes Completos:** O frontend é apenas um facilitador de UX. A disponibilidade, horários de funcionamento, intervalos de almoço e atribuição de profissionais são 100% validados no servidor através do `BookingService` utilizando objetos completos `datetime` (mitigando fugas em viragens de dia ou meia-noite como 23:45 + 30m). A granularidade de início de slots é fixada em intervalos regulares de 30 minutos.
2. **Proteção Contra Concorrência (Double-Booking):** As operações de agendamento correm sob transações atómicas (`transaction.atomic`) com bloqueio pessimista ao nível da linha (`select_for_update`) dos profissionais envolvidos (ordenados deterministicamente por ID), impedindo que duas threads ou pedidos simultâneos reservem o mesmo slot ou intervalos sobrepostos.
3. **Validação no Django Admin:** O `AppointmentAdminForm` submete qualquer criação ou edição manual de marcações no painel de administração às mesmas regras de validação (horário do negócio, almoço, durações e deteção de colisões com exclusão segura do próprio registo em edições).
4. **Alocação de Profissionais Segura:** Se não existirem profissionais ativos no sistema, marcações públicas falham explicitamente com `StaffUnavailableError`, nunca gerando registos com `staff_member=NULL`.
5. **Máquina de Estados e Estado Neutro `Aguardando Fecho`:** O comando `close_past_appointments` nunca assume arbitrariamente o sucesso de uma marcação passada como `Concluída`. Em vez disso, transita-a para o estado neutro `Aguardando Fecho`, cabendo aos funcionários confirmar se o cliente compareceu (`Concluída`) ou faltou (`Faltou`).
6. **Prevenção de Stored XSS:** No calendário de administração, os dados de clientes e serviços são construídos estritamente através da API DOM nativa (`document.createElement` e `textContent`), sem recurso a injeção em template strings ou HTML arbitrário.
7. **Sem Credenciais Hardcoded:** Não existem utilizadores pré-configurados com passwords previsíveis (`admin / admin`). A criação do superuser inicial via `seed_data` valida a palavra-passe através dos validadores nativos do Django (`validate_password()`).
8. **Mitigação de Host Header Poisoning:** Links de recuperação de palavra-passe são gerados utilizando o host canónico configurado no servidor (`CANONICAL_HOST` / `APP_BASE_URL`), eliminando o risco de envenenamento de cabeçalho `Host`.
9. **Integridade Histórica e Proteção:** Clientes (`User`), profissionais (`StaffMember`), serviços (`Service`) e categorias possuem proteção contra eliminação em cascata (`on_delete=models.PROTECT`). Marcações contêm snapshots imutáveis (`price_at_booking`, `service_name_at_booking`, `duration_at_booking`), garantindo que alterações de preçário ou desativação de catálogo não adulteram o histórico financeiro.
10. **Aceitação Obrigatória de Termos (Social Login):** Utilizadores que acedam via Google OAuth sem termos aceites no perfil são obrigatoriamente redirecionados para `/complete-profile/` antes de poderem aceder à área pessoal ou realizar agendamentos.
11. **Rate Limiting Distribuído:** Autenticação (Login), Registo, Recuperação de Palavra-passe, Agendamento, Cancelamento e Testemunhos estão protegidos contra abuso por rate limiting baseado em IP e utilizador, com suporte a proxies de confiança (Render) e cache partilhada.
12. **Unicidade de Email ao Nível da Base de Dados:** Índice único funcional `LOWER(email)` aplicado na tabela `auth_user` para assegurar que registos concorrentes não criam contas duplicadas.

---

## ⚙️ Variáveis de Ambiente

Crie um ficheiro `.env` na raiz do projeto com base no modelo fornecido em `.env.example`:

### Variáveis Obrigatórias em Produção

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `DEBUG` | Modo de depuração (deve ser obrigatoriamente `False`) | `False` |
| `SECRET_KEY` | Chave criptográfica única e segura do Django | *(50+ carateres aleatórios)* |
| `DATABASE_URL` | URL de ligação PostgreSQL (Neon / RDS) | `postgresql://user:pass@host:5432/db?sslmode=require` |
| `ALLOWED_HOSTS` | Domínios autorizados separados por vírgula (sem `*`) | `meusalao.com,www.meusalao.com,.onrender.com` |
| `CANONICAL_HOST` | Domínio canónico para emails e links transacionais | `meusalao.com` |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para proteção CSRF em HTTPS | `https://meusalao.com,https://*.onrender.com` |

### Variáveis de Email (Necessárias para Envio de Recuperação de Password)

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `EMAIL_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `EMAIL_PORT` | Porta SMTP | `587` |
| `EMAIL_HOST_USER` | Email remetente | `suporte@meusalao.com` |
| `EMAIL_HOST_PASSWORD` | Password de aplicação do email | `xxxx xxxx xxxx xxxx` |
| `EMAIL_USE_TLS` | Encriptação STARTTLS | `True` |
| `DEFAULT_FROM_EMAIL` | Remetente padrão | `VexyloSchedule <suporte@meusalao.com>` |

### Variáveis Opcionais

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `GOOGLE_CLIENT_ID` | Client ID do Google Cloud Console para OAuth | `123456...apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Client Secret do Google Cloud Console | `GOCSPX-...` |
| `CREATE_INITIAL_SUPERUSER` | Ativa a criação do admin inicial via `seed_data` | `false` ou `true` |
| `INITIAL_SUPERUSER_USERNAME` | Nome de utilizador do superuser inicial | `admin_gestor` |
| `INITIAL_SUPERUSER_EMAIL` | Email do superuser inicial | `admin@meusalao.com` |
| `INITIAL_SUPERUSER_PASSWORD` | Password forte para o superuser inicial | `MinhaPassForte2026!` |
| `LOG_LEVEL` | Nível de detalhe do logging | `INFO` |

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
npm install
npm run build:css
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

*(O comando `seed_data` é idempotente e cria os horários base — com Quarta-feira e Domingo encerrados por omissão — sem sobrescrever configurações existentes).*

### 5. Iniciar o Servidor de Desenvolvimento

```bash
python manage.py runserver 8000
```
Aceda ao site em `http://127.0.0.1:8000/` e à área de gestão em `http://127.0.0.1:8000/vexylo-admin/`.

---

## 🧪 Testes Automatizados

Para executar a suite completa de testes em ambiente local (utilizando base de dados em memória):

```bash
python manage.py test
```

### Testes de Concorrência com PostgreSQL Real

Para validar a integridade de bloqueios sob concorrência real (com threads concorrentes sincronizadas via `threading.Barrier`):

```bash
# Definir a variável e apontar para uma base PostgreSQL (ex: Neon):
$env:USE_REAL_POSTGRES_TESTS="true"
python manage.py test website.tests.test_concurrency --noinput -v 2
```

### Verificações de Qualidade e Segurança de Deploy

```bash
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
pip check
```

---

## 🐳 Execução com Docker Multi-Stage

O `Dockerfile` implementa um build multi-stage em três fases:
1. **Builder Frontend:** Compila os estilos Tailwind com Node.js e gera o CSS minificado para produção.
2. **Builder Python:** Compila e descarrega as wheels das dependências Python (`gcc`, `libpq-dev`).
3. **Runtime Slim:** Imagem mínima baseada em `python:3.11-slim` contendo apenas `curl` e `libpq5`, executada como utilizador não-root `appuser`.

```bash
# Construir a imagem
docker build -t vexyloschedule:latest .

# Executar o contentor
docker run -d --name vexylo -p 8000:8000 --env-file .env vexyloschedule:latest
```

---

## ⏰ Tarefas de Manutenção (Cron / Tarefas em Segundo Plano)

Para atualizar o estado de marcações que já decorreram para o estado neutro `Aguardando Fecho`:

```bash
# Simulação sem alteração (dry-run):
python manage.py close_past_appointments --dry-run

# Execução automática em cron diário:
python manage.py close_past_appointments
```

---

## 📋 Checklist Manual Antes de Entrar em Produção

- [ ] Variáveis `.env` preenchidas com `DEBUG=False` e `SECRET_KEY` aleatória forte.
- [ ] Informações de contacto da empresa (`BusinessInfo`) configuradas no Django Admin com morada e telefone reais.
- [ ] Horários de funcionamento e pausas de almoço revistos em `BusinessOpeningHours`.
- [ ] Credenciais SMTP testadas para envio real de recuperação de password.
- [ ] Google OAuth configurado na consola Google Cloud com as URIs de redirecionamento autorizadas.
- [ ] Superuser de produção criado com password segura e 2FA ativado se aplicável.
- [ ] Migrações aplicadas na base de dados PostgreSQL (`python manage.py migrate`).
- [ ] Ficheiros estáticos compilados e recolhidos (`npm run build:css && python manage.py collectstatic`).
- [ ] Certificado SSL/HTTPS ativo no domínio de produção.
