# Histórico de Atividades e Auditoria de Produção - VexyloSchedule

Este ficheiro documenta detalhadamente todos os prompts recebidos, as ações tomadas, os ficheiros criados/modificados (com indicação dos caminhos e linhas afetadas) e as validações realizadas para garantir a segurança, robustez e conformidade do VexyloSchedule.

---

## [2026-09-29] Auditoria Completa de Segurança, Hardening de Produção e Refatoração

### Prompt do Utilizador:
> Refatoração completa de produção, auditoria de segurança e hardening do VexyloSchedule:
> 1. Inspeção do repositório
> 2. Verificação de todas as falhas reportadas
> 3. Descoberta de problemas adicionais
> 4. Implementação direta dos fixes
> 5. Preservação de UX/UI
> 6. Adição de testes automatizados abrangentes
> 7. Execução dos checks e testes Django
> 8. Correção de falhas
> 9. Deixar o projeto substancialmente mais seguro e pronto para produção (44 requisitos).

---

### Ações e Alterações Realizadas:

#### 1. Upgrade para Django 5.2 LTS e Pinagem de Dependências
- **Ficheiro modificado:** `requirements.txt` (linhas 1 a 15)
  - Django atualizado para `Django==5.2.17` (LTS estável).
  - Todas as dependências diretas foram pinadas (`gunicorn==21.2.0`, `django-jazzmin==3.0.0`, `whitenoise==6.6.0`, `psycopg2-binary==2.9.12`, `django-allauth==65.19.4`, `requests==2.34.2`, `pyjwt==2.10.1`, `cryptography==48.0.0`, `python-dotenv==1.2.2`, `dj-database-url==3.1.2`).
  - Python 3.11/3.12 documentado.

#### 2. Configurações de Produção Fail-Safe e Segurança de Rede
- **Ficheiro modificado:** `core/settings.py` (linhas 18 a 268)
  - `DEBUG` com parsing robusto booleano que falha por omissão para `False`.
  - `SECRET_KEY` e `DATABASE_URL` obrigatórios em produção, disparando `ImproperlyConfigured` sem geração silenciosa de chaves efémeras nem fallback para SQLite em produção.
  - `ALLOWED_HOSTS`: Proibido `["*"]` em produção. Configuração de `CANONICAL_HOST` seguro.
  - Segurança de Cookies e Transporte: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` ativados em produção (`DEBUG=False`).
  - Segurança Allauth: `SOCIALACCOUNT_LOGIN_ON_GET = False` (prevenção de CSRF login), `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, e desativação de `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT` para evitar auto-conexão sem verificação.
  - Logging estruturado: handlers e loggers configurados para console/produção, com filtro de exceções e mascaramento de dados sensíveis.

#### 3. Eliminação do Superuser Padrão `admin / admin`
- **Ficheiro modificado:** `website/management/commands/seed_data.py` (linhas 16 a 48)
  - Removida completamente a criação cega de superusers com password "admin".
  - Implementado mecanismo opt-in seguro via variável `CREATE_INITIAL_SUPERUSER=true`, exigindo `INITIAL_SUPERUSER_USERNAME` e `INITIAL_SUPERUSER_PASSWORD` com validação de complexidade (mínimo 8 caracteres e rejeição de senhas fracas).
  - Removida qualquer impressão de credenciais em logs ou stdout.

#### 4. Correção do Stored XSS e Polling no Calendário Admin
- **Ficheiro modificado:** `website/templates/admin/website/appointment/change_list.html` (linhas 258 a 345)
  - Eliminada a interpolação de strings HTML `${props.client_name}` e `${props.service_name}` com `{ html: ... }`.
  - Implementada renderização nativa via DOM API segura (`document.createElement`, `textContent`) retornando nós DOM `{ domNodes: [card] }`.
  - Polling FullCalendar otimizado para respeitar a Page Visibility API (`!document.hidden`), com intervalo de 30 segundos e debounce para evitar sobreposição de requisições.

#### 5. Correção do Password Reset (Host Header Poisoning e Envio Duplo de E-mail)
- **Ficheiro modificado:** `website/views.py` (linhas 45 a 95)
  - Eliminada a chamada duplicada a `super().form_valid(form)` após `form.save(...)`, garantindo o envio estrito de exatamente 1 e-mail de redefinição.
  - Validação estrita de `domain_override` utilizando `settings.CANONICAL_HOST` ou hosts permitidos em `ALLOWED_HOSTS`, prevenindo ataques de envenenamento de cabeçalho Host.

#### 6. Modelo de Dados, Snapshots Históricos e Restrições de Integridade
- **Ficheiro modificado:** `website/models.py` (linhas 1 a 440)
  - Proteção de Chaves Estrangeiras: `on_delete=models.PROTECT` aplicado em `Service.category` e `Appointment.service` para evitar a destruição de dados históricos em manutenções de catálogo.
  - Soft-deactivation: Adicionado `is_active = models.BooleanField(default=True)` em `Service` e `StaffMember`.
  - Snapshots Históricos em `Appointment`: Criados os campos `service_name_at_booking`, `price_at_booking` e `duration_at_booking` preenchidos no momento da marcação.
  - Modelo Estruturado de Horários de Funcionamento: Criado `BusinessOpeningHours` com os 7 dias da semana (0-6), horário de abertura, fecho, e intervalos de almoço configuráveis.
  - Singleton `BusinessInfo`: Implementado `get_solo()` e sobrescrito `save()` para garantir estritamente no máximo uma instância na base de dados.
  - Restrições a Nível de Base de Dados (`CheckConstraint`):
    - `price >= 0` em `Service`.
    - `duration > 0` em `Service`.
    - `cancel_limit_hours >= 0` em `BusinessInfo`.
    - `rating BETWEEN 1 AND 5` em `Testimonial`.
  - Índices Compostos: Adicionados índices em `Appointment` para `[date, staff_member, status]` e `[user, date]`.

#### 7. Migrações de Esquema e Dados
- **Ficheiro criado:** `website/migrations/0003_businessopeninghours_alter_testimonial_options_and_more.py`
  - Aplica novos modelos, campos de snapshot, `is_active`, constraints e índices.
- **Ficheiro criado:** `website/migrations/0004_backfill_snapshots_and_hours.py`
  - Migração de dados segura que preenche retroativamente os snapshots de todos os agendamentos existentes com base no serviço associado e popula os 7 dias de funcionamento da empresa a partir do `BusinessInfo` existente.

#### 8. Serviço de Domínio de Marcações e Prevenção de Concorrência
- **Ficheiro criado:** `website/services/booking.py` (linhas 1 a 240)
  - Classe `BookingService` centralizada para validação de disponibilidade e criação transacional de agendamentos.
  - Concurrency Lock: Utilização de `transaction.atomic()` e `select_for_update()` na linha do `StaffMember` para prevenir reservas duplas ou simultâneas (race conditions).
  - Validação de intervalo de sobreposição: `existing_start < requested_end AND existing_end > requested_start`.
  - Validação estrita server-side: verificação de datas passadas, dias fechados, horário de funcionamento, intervalo de almoço, profissionais ativos e alocação automática para a opção "Qualquer Profissional".

#### 9. Utilitário de Rate Limiting
- **Ficheiro criado:** `website/utils/ratelimit.py` (linhas 1 a 60)
  - Decorador `@rate_limit` baseado na cache do Django para proteção de endpoints sensíveis (registo, marcação, cancelamento e testemunhos).

#### 10. Limpeza e Refatoração de Views
- **Ficheiro modificado:** `website/views.py` (linhas 1 a 455)
  - Remoção de mais de 130 linhas de código morto e funções duplicadas (`home_view`, `register_view`, `book_appointment_view`, etc.).
  - Remoção de efeitos secundários (mutações de dados) no método GET de `admin_dashboard_api_view`.
  - Integração do `book_appointment_view` com o `BookingService`.
  - Enforçamento no lado do servidor das regras de cancelamento em `cancel_appointment_view` com verificação de proprietário, estado do agendamento e limite horário configurado (`can_be_cancelled`).
  - Moderação obrigatória de testemunhos (`is_visible = False` por omissão), vinculação ao utilizador autenticado e tratamento seguro de exceções sem fuga de detalhes internos.

#### 11. Painel de Administração e Fecho de Agendamentos
- **Ficheiros modificados:**
  - `website/admin.py` (linhas 1 a 180): Adicionado inline `BusinessOpeningHoursInline` no `BusinessInfoAdmin` com bloqueio a novas adições (singleton), filtros por `is_active` e ações administrativas explícitas para transições de estado (`Confirmar`, `Concluir`, `Marcar Falta`, `Cancelar`).
  - `website/management/commands/close_past_appointments.py` (linhas 1 a 65): Adicionado suporte a `--dry-run` e `--target-status`, removendo encerramento automático cego e documentando execução via cron/scheduler externo.

#### 12. Interface de Utilizador e Templates
- **Ficheiros modificados:**
  - `website/templates/website/dashboard.html` (linhas 45 a 85): Apresentação correta dos 5 estados (`Pendente`, `Confirmada`, `Concluída`, `Faltou`, `Cancelada`), exibindo o botão de cancelamento apenas para estados elegíveis.
  - `website/templates/website/book_appointment.html` (linhas 180 a 220): Flatpickr recebe dinamicamente os dias encerrados a partir do backend (`closed_weekdays_js`), eliminando dias hardcoded no frontend.
  - `website/templates/website/terms_conditions.html` (linhas 12 a 25 e 60 a 70): Horas de cancelamento dinâmicas a partir do `BusinessInfo` e remoção da data falsa diária `{% now %}` por data fixa do documento.
  - `website/templates/website/privacy_policy.html` (linhas 12 a 25): Data estática de revisão e esclarecimento técnico sobre partilha com fornecedores de infraestrutura/OAuth.
  - `website/templates/website/base.html` (linhas 15 a 30 e 240 a 275): Pinagem das versões de CDN (Chart.js, FullCalendar, Flatpickr, Font Awesome) e banner de cookies focado na transparência técnica de cookies essenciais de sessão/CSRF.

#### 13. Hardening Docker e Startup
- **Ficheiros modificados:**
  - `Dockerfile` (linhas 1 a 48): Configuração multi-stage, criação e execução sob utilizador não privilegiado `appuser`, remoção de dependências de compilação na imagem final e inclusão de diretiva `HEALTHCHECK`.
  - `entrypoint.sh` (linhas 1 a 24): Ativado `set -euo pipefail`, mantendo migrações idempotentes e removendo a execução cega de comandos de encerramento de agendamentos no arranque.

#### 14. Suíte Abrangente de Testes Automatizados
- **Ficheiros criados:**
  - `website/tests/__init__.py`
  - `website/tests/test_auth.py`: Registo, rejeição de e-mail duplicado (case-insensitive), envio único de password reset e proteção contra Host poisoning.
  - `website/tests/test_booking.py`: Validações de agendamento em datas passadas, dias encerrados, fora do horário, sobreposição de almoço, sobreposição de horários/durações, atribuição de qualquer profissional e isolamento de marcações canceladas.
  - `website/tests/test_cancellation.py`: Cancelamento por proprietário, rejeição para utilizadores terceiros, respeito ao limite de horas, e rejeição para agendamentos já concluídos/faltas.
  - `website/tests/test_models.py`: Preços negativos, durações inválidas, snapshots históricos preservados e integridade de chave estrangeira com PROTECT.
  - `website/tests/test_security.py`: Prevenção de XSS no admin calendar e sanitização de payloads maliciosos.
  - `website/tests/test_testimonials.py`: Moderação padrão (`is_visible=False`), bloqueio a utilizadores anónimos e limites de pontuação.
- **Resultado da execução dos testes:**
  - `Ran 38 tests in 16.464s — OK (Todos os 38 testes passaram com sucesso).`

#### 15. Integração Contínua (CI) e Documentação
- **Ficheiros criados/modificados:**
  - `.github/workflows/ci.yml`: Pipeline com serviço PostgreSQL, verificação de ambiente, `check`, `check --deploy`, verificação de migrações e execução dos testes.
  - `.env.example`: Modelo de variáveis de ambiente de produção e desenvolvimento seguro.
  - `README.md` (linhas 1 a 184): Documentação completa de arquitetura, instalação, variáveis, comandos e boas práticas.

---

## [2026-09-30] Segunda Passagem Completa de Hardening, Auditoria Adversarial e Correção de Invariantes

### Prompt do Utilizador:
> # VexyloSchedule — SECOND FULL PRODUCTION HARDENING PASS
> 1. Inspecionar o repositório como existe agora e verificar os problemas reportados contra o código real.
> 2. Preservar correções válidas existentes.
> 3. Corrigir todas as questões confirmadas (135 itens e diretrizes adversariais).
> 4. Corrigir cálculo de agendamentos trans-meia-noite (usar datetimes completos).
> 5. Garantir testes de concorrência com PostgreSQL real e sincronização `threading.Barrier`.
> 6. Tratar 0 profissionais ativos com `StaffUnavailableError` (sem criar `staff_member=NULL`).
> 7. Submeter o Django Admin (`AppointmentAdminForm`) às regras de agendamento e disponibilidade.
> 8. Reforçar máquina de estados com o estado neutro `Aguardando Fecho` (sem inferir `Concluída` automaticamente).
> 9. Assegurar unicidade case-insensitive de e-mail ao nível da base de dados (`LOWER(email)`).
> 10. Exigir aceitação de Termos e Privacidade para utilizadores Google OAuth (`TermsAcceptanceMiddleware` + `/complete-profile/`).
> 11. Rate limiting no Login e Password Reset com suporte a proxies de confiança e cache partilhada.
> 12. Modernizar armazenamento estático para Django 5.2 `STORAGES`.
> 13. Compilação local de Tailwind CSS sem Play CDN (`package.json`, `tailwind.config.js`).
> 14. Commit do `.env.example` e ajuste do `.gitignore`.
> 15. Dockerfile multi-stage real (3 fases) sem compiladores na imagem final runtime.
> 16. Sincronizar e tornar verídico o `README.md` e `LOGS.md`.

---

### Ações e Alterações Realizadas:

#### 1. Remoção do Tailwind Play CDN e Criação do Build Local de Frontend
- **Ficheiro criado:** `package.json` (linhas 1 a 20)
  - Configuração npm com `tailwindcss@^3.4.17` e script `"build:css": "tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify"`.
- **Ficheiro criado:** `tailwind.config.js` (linhas 1 a 28)
  - Scan de todos os templates em `website/templates/**/*.html` e `static/js/**/*.js` com paleta de cores (`primary`, `bgSoft`, etc.).
- **Ficheiro criado:** `static/css/input.css` (linhas 1 a 15)
  - Diretivas `@tailwind base;`, `@tailwind components;`, `@tailwind utilities;`.
- **Ficheiro gerado:** `static/css/tailwind.css`
  - CSS minificado compilado (~25KB).
- **Ficheiro modificado:** `website/templates/website/base.html` (linhas 15 a 30)
  - Removido `<script src="https://cdn.tailwindcss.com"></script>` e configuração inline `tailwind.config`.
  - Adicionado `<link rel="stylesheet" href="{% static 'css/tailwind.css' %}">`.
- **Ficheiro modificado:** `.gitignore` (linhas 8 a 15)
  - Adicionado `node_modules/` e `!.env.example`.

#### 2. Modernização de Storage para Django 5.2 (`STORAGES`) e Cache de Produção
- **Ficheiro modificado:** `core/settings.py` (linhas 85 a 265)
  - Substituído `STATICFILES_STORAGE` obsoleto pelo dicionário moderno `STORAGES` com `CompressedManifestStaticFilesStorage`.
  - Configurada `CACHES` com `DatabaseCache` (`django_cache_table`) em produção para partilha de rate limits entre múltiplos workers Gunicorn, mantendo `LocMemCache` para desenvolvimento e testes.
  - Implementado parsing e validação rigorosa de `CANONICAL_HOST` e `APP_BASE_URL`.
  - Tornada a autenticação Google OAuth condicional através de `GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)`.
  - Configurado fail-fast para envio de email em produção (`REQUIRE_EMAIL_IN_PROD`).
  - Adicionado `TermsAcceptanceMiddleware` aos `MIDDLEWARE`.

#### 3. Validação de Agendamento com Datetimes Completos e Granularidade de Slots
- **Ficheiro modificado:** `website/services/booking.py` (linhas 1 a 260)
  - Eliminado o descarte de datas via `.time()`. A validação agora combina `target_date` e horários em objetos `datetime` conscientes (`start_dt`, `end_dt`, `open_dt`, `close_dt`, `lunch_start_dt`, `lunch_end_dt`).
  - Rejeição estrita de agendamentos trans-meia-noite (`end_dt.date() != target_date`), como `23:45 + 30m`.
  - Granularidade de slots obrigatória: início restrito a intervalos regulares de 30 minutos (00 ou 30 minutos), rejeitando horários arbitrários (ex: 10:07, 10:13, 10:29).
  - Rejeição explícita com `StaffUnavailableError` caso existam 0 profissionais ativos no sistema, nunca criando `Appointment.staff_member = NULL`.
  - Ordenação determinística por ID no bloqueio pessimista `select_for_update()` para prevenir deadlocks de transações concorrentes.

#### 4. Validação de Agendamentos no Django Admin (`AppointmentAdminForm`)
- **Ficheiro modificado:** `website/forms.py` (linhas 64 a 158)
  - Criado `AppointmentAdminForm` com validação completa de horários de funcionamento, almoço, durações e colisão com outros agendamentos do mesmo profissional.
  - Na edição de agendamentos existentes, a própria marcação (`self.instance.pk`) é excluída da verificação de colisão, permitindo aos administradores editar detalhes sem falsos positivos de conflito.
  - Criado `CompleteProfileForm` para recolha de telefone e aceitação explícita dos Termos e Condições e Política de Privacidade.
- **Ficheiro modificado:** `website/admin.py` (linhas 30 a 115)
  - Registado `AppointmentAdminForm` no `AppointmentAdmin`.
  - Adicionado badge visual roxo para o novo estado `Aguardando Fecho`.

#### 5. Máquina de Estados Reforçada e Estado Neutro `Aguardando Fecho`
- **Ficheiro modificado:** `website/models.py` (linhas 15 a 360)
  - Adicionado estado `'Aguardando Fecho'` às opções de `Appointment.STATUS_CHOICES`.
  - Atualizado `VALID_TRANSITIONS` para suportar `Confirmada -> Aguardando Fecho`, `Aguardando Fecho -> Concluída`, `Aguardando Fecho -> Faltou`.
  - Enforçado no método `clean()` e `transition_to()` a proibição de transições inválidas (ex: `Cancelada -> Confirmada`, `Concluída -> Pendente`).
  - Atualizado `save()` de `Appointment` para recalcular dinamicamente `end_time` caso a hora ou a duração sejam alteradas, prevenindo valores obsoletos.
  - Proteção contra eliminação acidental: `Appointment.user` e `Appointment.staff_member` configurados com `on_delete=models.PROTECT`.
  - Singleton `BusinessInfo`: enforçado no `save()` que a tentativa de criar um segundo registo lança `ValidationError`. O método `BusinessInfo.get_solo()` retorna uma instância não-salva em memória sem mutar a base de dados em leituras GET. Adicionada propriedade `clean_whatsapp` que normaliza o número para URLs do WhatsApp.
  - CheckConstraints adicionadas na BD para `BusinessOpeningHours` (`weekday` entre 0 e 6, `opening_time < closing_time`) e `Service` (`duration` entre 5 e 480 minutos).
- **Ficheiro modificado:** `website/management/commands/close_past_appointments.py` (linhas 15 a 65)
  - O comando agora tem por padrão `target_status = 'Aguardando Fecho'`, invocando o método autoritativo `transition_to()` e `save()`, sem fabricar desfechos de sucesso arbitrários.

#### 6. Unicidade de Email na BD e Migração de Dados
- **Ficheiro criado:** `website/migrations/0005_remove_businessinfo_business_cancel_limit_positive_and_more.py`
  - Adiciona restrições e campos para o novo estado `Aguardando Fecho`.
  - Executa verificação de dados para garantir que não existem e-mails duplicados case-insensitively na tabela `auth_user`.
  - Cria índice único funcional na base de dados PostgreSQL (`unique_user_email_ci`) sobre `LOWER(email)`.
  - Atualiza os horários base garantindo que Quarta-feira e Domingo permanecem encerrados por omissão, preservando o comportamento histórico da aplicação.

#### 7. Aceitação Obrigatória de Termos para Utilizadores de Login Social
- **Ficheiro criado:** `website/middleware.py` (linhas 1 a 35)
  - `TermsAcceptanceMiddleware`: interceta qualquer utilizador autenticado sem `terms_accepted_at` ou `privacy_policy_accepted_at` ao tentar aceder a áreas protegidas (`/dashboard/`, `/book/`, `/cancel/`, `/api/submit-testimonial/`), redirecionando-o para `/complete-profile/?next=...`.
- **Ficheiro modificado:** `website/views.py` (linhas 54 a 120 e 280 a 380)
  - Adicionada view `complete_profile_view` que processa o formulário de aceitação de termos e telefone, gravando os timestamps de consentimento.
  - Substituída a interpolação bizarra no `home_view` por um Django `Prefetch` limpo e canónico de serviços ativos (`Service.objects.filter(is_active=True)`).
  - API `get_available_times`: retorna HTTP 400 Bad Request se IDs ou datas forem inválidos (em vez de retornar 200 com lista vazia).
  - API `api_calendar_events`: datas de início e fim tratadas com semântica correta ISO e fim exclusivo (`date__lt=end_date`), revertendo URLs do admin com `reverse()` em vez de caminho hardcoded.
  - API `cancel_appointment_view`: valida server-side os motivos de cancelamento contra uma lista controlada de opções.
  - API `admin_dashboard_api_view`: cálculo de `top_services` utiliza o snapshot histórico `service_name_at_booking`.
- **Ficheiro criado:** `website/templates/website/complete_profile.html` (linhas 1 a 70)
  - Template de finalização de perfil para utilizadores sociais com checkboxes de consentimento legal.

#### 8. Rate Limiting no Login e Password Reset com Proteção Anti-Spoofing
- **Ficheiro modificado:** `website/utils/ratelimit.py` (linhas 1 a 75)
  - `get_client_ip`: em ambiente de produção (com `SECURE_PROXY_SSL_HEADER` / Render) extrai o primeiro IP de `HTTP_X_FORWARDED_FOR`; em ambiente direto confia em `REMOTE_ADDR`, eliminando vulnerabilidades de spoofing de IP.
  - Resposta padrão HTTP 429 Too Many Requests quando o limite é excedido.
- **Ficheiro modificado:** `website/views.py` (linhas 54 a 70)
  - Criada classe `CustomLoginView` herdando de `auth_views.LoginView` com `@rate_limit('login', limit=5, period=300)`.
  - Rate limiting aplicado também a `register` e `submit_testimonial`.

#### 9. Dockerfile Multi-Stage Real e Segurança CI
- **Ficheiro modificado:** `Dockerfile` (linhas 1 a 65)
  - Etapa 1 (`frontend-builder`): `node:20-slim`, executa `npm ci` e compila `tailwind.css`.
  - Etapa 2 (`python-builder`): `python:3.11-slim`, instala compiladores temporários (`gcc`, `libpq-dev`) e compila wheels em `/install`.
  - Etapa 3 (`runtime`): `python:3.11-slim`, copia wheels pré-compiladas e assets estáticos, instala apenas `curl` e `libpq5`, e executa como utilizador não-root `appuser`.
- **Ficheiro criado:** `.dockerignore` (linhas 1 a 25)
  - Ignora `.env`, `.env.*`, `.git`, `db.sqlite3`, `staticfiles`, `node_modules`, `__pycache__`.
- **Ficheiro modificado:** `.github/workflows/ci.yml` (linhas 1 a 85)
  - Healthcheck do serviço PostgreSQL corrigido para usar o utilizador configurado (`pg_isready -U vexylo_user -d test_vexylo`).
  - Adicionado build de frontend (`npm ci && npm run build:css`).
  - Adicionado `pip check` e compilação de estáticos (`python manage.py collectstatic --noinput`).
  - Adicionado `python manage.py check --deploy` com variáveis completas de produção.
  - Execução dos testes de concorrência com `USE_REAL_POSTGRES_TESTS: "true"`.
  - Adicionado passo de verificação de build Docker (`docker build -t vexylo:ci .`).

#### 10. Testes Automatizados e Concorrência Real com PostgreSQL
- **Ficheiros modificados/criados em `website/tests/`:**
  - `test_concurrency.py`: reestruturado com `threading.Barrier(2)` para corrida simultânea em threads reais contra PostgreSQL. Testa colisão de slots idênticos (10:00-10:30 vs 10:00-10:30), intervalos sobrepostos com durações diferentes (10:00-11:00 vs 10:30-11:00) e atribuição de "Qualquer Profissional" quando apenas um está livre.
  - `test_booking.py`: adicionados testes para agendamento às 23:45 (+30m) ultrapassando a meia-noite (rejeitado), limite exato de fecho (18:45 vs 18:30 com fecho às 19:00), 0 profissionais ativos lançando `StaffUnavailableError`, granularidade de 30 minutos (10:07, 10:13 rejeitados), validações no `AppointmentAdminForm` e HTTP 400 em parâmetros inválidos da API.
  - `test_auth.py`: adicionados testes de aceitação de termos para utilizadores de login social com redirecionamento para `/complete-profile/`, e rate limiting de login (HTTP 429 após 5 tentativas).
  - `test_models.py`: adicionados testes para o estado `'Aguardando Fecho'`, validação da máquina de estados, idempotência do `close_past_appointments`, proteção de eliminação de clientes e profissionais com `PROTECT`, e segurança de leitura em `BusinessInfo.get_solo()`.
  - `test_security_xss.py`: adicionado teste estático de regressão que verifica que o template do calendário admin não contém `{ html:`, `innerHTML =` nem `${props.client_name}` e utiliza `.textContent`.

---

### Resultados Oficiais dos Testes e Comandos:

1. **Testes Unitários e de Integração:**
   - `python manage.py test`
   - **Resultado:** `Ran 52 tests in 26.545s — OK (Todos os 52 testes passaram sem erros nem falhas).`

2. **Testes de Concorrência com PostgreSQL Real (Neon Serverless):**
   - `$env:USE_REAL_POSTGRES_TESTS="true"; python manage.py test website.tests.test_concurrency --noinput -v 2`
   - **Base de Dados:** PostgreSQL 18.x (`connection.vendor == 'postgresql'`)
   - **Resultado:**
     - `test_concurrent_any_staff_race_with_single_available_professional ... ok`
     - `test_concurrent_identical_slot_race ... ok`
     - `test_concurrent_overlapping_durations_race ... ok`
     - `Ran 3 tests in 47.432s — OK.`
     - **Comportamento Comprovado:** Duas threads disputaram exatamente o mesmo slot/intervalo com `threading.Barrier`. Em cada cenário, exatamente 1 transação fez commit com sucesso e exatamente 1 requisição falhou com `SlotOccupiedError`. Total de marcações ativas na BD = 1.

3. **Verificações do Sistema e Deploy:**
   - `python manage.py check`: `System check identified no issues (0 silenced).`
   - `python manage.py makemigrations --check --dry-run`: `No changes detected.`
   - `python manage.py check --deploy`: `System check identified no issues (0 silenced).` (Zero avisos com variáveis de produção ativas).
   - `python manage.py collectstatic --noinput`: `0 static files copied, 196 unmodified, 512 post-processed.`
   - `pip check`: `No broken requirements found.`
   - `npm run build:css`: Tailwind CSS compilado e minificado em 317ms.
