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
