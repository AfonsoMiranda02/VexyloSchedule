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
