from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from website.models import UserProfile

class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.password_reset_url = reverse('password_reset')

    def test_registration_success_and_terms_recorded(self):
        """Registo bem sucedido com registo de timestamps de aceitação de termos."""
        payload = {
            'username': 'novocliente',
            'first_name': 'Novo',
            'email': 'novo@exemplo.com',
            'phone': '912345678',
            'password1': 'SenhaForte123!',
            'password2': 'SenhaForte123!',
            'accept_terms': 'on'
        }
        response = self.client.post(self.register_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)
        
        user = User.objects.filter(username='novocliente').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'novo@exemplo.com')
        
        profile = UserProfile.objects.filter(user=user).first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.phone, '912345678')
        self.assertIsNotNone(profile.terms_accepted_at)
        self.assertIsNotNone(profile.privacy_policy_accepted_at)

    def test_registration_duplicate_email_rejected(self):
        """Registo com email já existente deve ser rejeitado."""
        User.objects.create_user(username='existente', email='existente@exemplo.com', password='Password123!')
        
        payload = {
            'username': 'novouser',
            'first_name': 'Novo',
            'email': 'existente@exemplo.com',
            'phone': '912345678',
            'password1': 'SenhaForte123!',
            'password2': 'SenhaForte123!',
            'accept_terms': 'on'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='novouser').exists())
        self.assertContains(response, "Este email já se encontra registado")

    def test_registration_case_insensitive_duplicate_email_rejected(self):
        """Email duplicado com maiúsculas/minúsculas deve ser rejeitado."""
        User.objects.create_user(username='existente', email='cliente@exemplo.com', password='Password123!')
        
        payload = {
            'username': 'outro_user',
            'first_name': 'Outro',
            'email': 'CLIENTE@EXEMPLO.COM',
            'phone': '912345678',
            'password1': 'SenhaForte123!',
            'password2': 'SenhaForte123!',
            'accept_terms': 'on'
        }
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='outro_user').exists())
        self.assertContains(response, "Este email já se encontra registado")

    @override_settings(
        CANONICAL_HOST='trusted-vexylo.com',
        ALLOWED_HOSTS=['trusted-vexylo.com', 'testserver', 'localhost', '127.0.0.1']
    )
    def test_password_reset_sends_exactly_one_email_and_uses_trusted_host(self):
        """Password reset deve enviar exatamente UM email usando o host fidedigno configurado."""
        User.objects.create_user(username='recuperar', email='recuperar@exemplo.com', password='OldPassword123!')
        
        mail.outbox.clear()
        
        # Simula pedido com cabeçalho Host padrão
        response = self.client.post(self.password_reset_url, {'email': 'recuperar@exemplo.com'}, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Garante que foi enviado EXATAMENTE 1 email (e não 2)
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ['recuperar@exemplo.com'])
        
        # Verifica se o link contém o domínio confiável configurado
        email_body = sent_email.body
        self.assertIn('trusted-vexylo.com', email_body)

    @override_settings(
        CANONICAL_HOST='app.vexyloschedule.com',
        ALLOWED_HOSTS=['app.vexyloschedule.com', 'testserver', 'localhost', '127.0.0.1']
    )
    def test_password_reset_host_header_poisoning_prevented(self):
        """Um atacante que tente injetar um cabeçalho Host malicioso não permitido é bloqueado com HTTP 400 Bad Request."""
        User.objects.create_user(username='vitima', email='vitima@exemplo.com', password='OldPassword123!')
        
        response = self.client.post(
            self.password_reset_url, 
            {'email': 'vitima@exemplo.com'},
            HTTP_HOST='attacker-domain.evil.com'
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(
        CANONICAL_HOST='canonical-vexylo.com',
        ALLOWED_HOSTS=['canonical-vexylo.com', 'another-allowed.com', 'testserver']
    )
    def test_password_reset_forces_canonical_host_even_if_alternative_host_used(self):
        """Mesmo que o pedido use outro host permitido, o link gerado usa obrigatoriamente o CANONICAL_HOST."""
        User.objects.create_user(username='vitima2', email='vitima2@exemplo.com', password='OldPassword123!')
        mail.outbox.clear()
        
        response = self.client.post(
            self.password_reset_url, 
            {'email': 'vitima2@exemplo.com'},
            HTTP_HOST='another-allowed.com'
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('canonical-vexylo.com', mail.outbox[0].body)
        self.assertNotIn('another-allowed.com', mail.outbox[0].body)

    def test_social_user_missing_terms_redirected_and_completed(self):
        """Utilizador com login social sem termos aceites é redirecionado para /complete-profile/ até aceitar."""
        social_user = User.objects.create_user(username='googleuser', email='guser@exemplo.com', password='Password123!')
        # Criar perfil sem termos aceites
        UserProfile.objects.create(user=social_user, phone='900000000')

        self.client.force_login(social_user)

        # 1. Tenta aceder ao dashboard -> Redirecionado para /complete-profile/
        dashboard_url = reverse('dashboard')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('complete_profile'), response.url)

        # 2. Submete o formulário com aceite de termos
        complete_url = reverse('complete_profile')
        post_response = self.client.post(complete_url, {
            'phone': '912345678',
            'accept_terms': 'on'
        })
        self.assertEqual(post_response.status_code, 302)

        # 3. Verifica se os timestamps foram guardados
        profile = UserProfile.objects.get(user=social_user)
        self.assertIsNotNone(profile.terms_accepted_at)
        self.assertIsNotNone(profile.privacy_policy_accepted_at)

        # 4. Acesso subsequente ao dashboard é permitido
        res_after = self.client.get(dashboard_url)
        self.assertEqual(res_after.status_code, 200)

    def test_login_rate_limiting_after_multiple_failures(self):
        """5 tentativas de login consecutivas falhadas ativam o rate limit (HTTP 429)."""
        from django.core.cache import cache
        cache.clear()

        login_url = reverse('login')
        payload = {'username': 'nonexistent', 'password': 'wrongpassword'}

        # 5 tentativas falhadas permitidas
        for i in range(5):
            res = self.client.post(login_url, payload)
            self.assertIn(res.status_code, [200, 302])

        # A 6ª tentativa deve ser bloqueada por rate limit
        res_blocked = self.client.post(login_url, payload)
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn(b"Demasiadas tentativas", res_blocked.content)

    @override_settings(
        APP_BASE_URL='http://localhost:8000',
        ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver']
    )
    def test_password_reset_app_base_url_port_preservation(self):
        """APP_BASE_URL deve preservar a porta de desenvolvimento (ex: localhost:8000) nos links de email."""
        User.objects.create_user(username='devuser', email='devuser@exemplo.com', password='Password123!')
        mail.outbox.clear()

        response = self.client.post(self.password_reset_url, {'email': 'devuser@exemplo.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('localhost:8000', mail.outbox[0].body)
        self.assertIn('http://', mail.outbox[0].body)

    @override_settings(
        APP_BASE_URL='https://vexylo.example.com',
        ALLOWED_HOSTS=['vexylo.example.com', 'testserver']
    )
    def test_password_reset_app_base_url_production_domain(self):
        """APP_BASE_URL de produção deve ser a fonte da verdade para o link de email, com protocolo HTTPS."""
        User.objects.create_user(username='produser', email='produser@exemplo.com', password='Password123!')
        mail.outbox.clear()

        response = self.client.post(self.password_reset_url, {'email': 'produser@exemplo.com'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://vexylo.example.com', mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend')
    def test_password_reset_dummy_backend_fails_safely(self):
        """Se o backend de email for DummyEmailBackend, a rota de password_reset não finge sucesso."""
        response = self.client.get(self.password_reset_url)
        self.assertEqual(response.status_code, 500)

    def test_terms_acceptance_preserves_safe_next_and_rejects_open_redirect(self):
        """O fluxo de termos preserva o destino 'next' seguro e rejeita open redirects maliciosos."""
        user = User.objects.create_user(username='social_next', email='social_next@exemplo.com', password='Password123!')
        UserProfile.objects.create(user=user)
        self.client.force_login(user)

        complete_url = reverse('complete_profile')

        # 1. Com next interno válido (/book/) -> Redireciona para /book/ após submissão
        res_valid = self.client.post(f"{complete_url}?next=/book/", {
            'phone': '912345678',
            'accept_terms': 'on',
            'next': '/book/'
        })
        self.assertRedirects(res_valid, '/book/')

        # 2. Com next externo malicioso (https://evil.example.com) -> Rejeitado e cai no dashboard
        user2 = User.objects.create_user(username='social_evil', email='social_evil@exemplo.com', password='Password123!')
        UserProfile.objects.create(user=user2)
        self.client.force_login(user2)

        res_evil = self.client.post(f"{complete_url}?next=https://evil.example.com", {
            'phone': '912345678',
            'accept_terms': 'on',
            'next': 'https://evil.example.com'
        })
        self.assertRedirects(res_evil, reverse('dashboard'))

    def test_registration_duplicate_email_integrity_error_handled_gracefully(self):
        """Se ocorrer uma colisão concorrente de email gerando IntegrityError, a view retorna erro no formulário sem 500."""
        from unittest.mock import patch
        from django.db import IntegrityError

        payload = {
            'username': 'novorace',
            'first_name': 'Novo',
            'email': 'race@exemplo.com',
            'phone': '912345678',
            'password1': 'SenhaForte123!',
            'password2': 'SenhaForte123!',
            'accept_terms': 'on'
        }

        # Simula IntegrityError no momento do form.save() devido a race condition na base de dados
        with patch('website.forms.UserRegisterForm.save') as mock_save:
            mock_save.side_effect = IntegrityError('duplicate key value violates unique constraint "unique_user_email_ci"')
            response = self.client.post(self.register_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este email já está registado.")

    def test_login_rate_limiting_isolated_by_account_hash(self):
        """Tentativas de login falhadas num utilizador não bloqueiam imediatamente outro utilizador no mesmo IP."""
        from django.core.cache import cache
        cache.clear()

        login_url = reverse('login')
        # 5 tentativas falhadas na conta 'user_alfa'
        for _ in range(5):
            self.client.post(login_url, {'username': 'user_alfa', 'password': 'wrong'})

        # 6ª tentativa para 'user_alfa' está bloqueada (429)
        res_alfa = self.client.post(login_url, {'username': 'user_alfa', 'password': 'wrong'})
        self.assertEqual(res_alfa.status_code, 429)

        # Tentativa para 'user_beta' a partir do mesmo cliente/IP deve continuar permitida (não é 429)
        res_beta = self.client.post(login_url, {'username': 'user_beta', 'password': 'wrong'})
        self.assertIn(res_beta.status_code, [200, 302])
