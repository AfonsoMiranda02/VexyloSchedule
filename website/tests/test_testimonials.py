import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from website.models import Testimonial, UserProfile

class TestimonialTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username='autor', password='Password123!')
        now = timezone.now()
        UserProfile.objects.create(user=self.user, terms_accepted_at=now, privacy_policy_accepted_at=now)
        self.url = reverse('submit_testimonial')

    def test_unauthenticated_submission_blocked(self):
        """Utilizadores não autenticados não podem submeter testemunhos."""
        response = self.client.post(
            self.url,
            json.dumps({'rating': 5, 'text': 'Excelente atendimento!'}),
            content_type='application/json'
        )
        # Redireciona para o login (302)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Testimonial.objects.count(), 0)

    def test_submission_defaults_to_moderation_hidden(self):
        """Testemunho submetido com sucesso deve ser gravado com is_visible=False por omissão."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            json.dumps({'rating': 5, 'text': 'Serviço 5 estrelas, recomendo muito!'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        testimonial = Testimonial.objects.filter(user=self.user).first()
        self.assertIsNotNone(testimonial)
        self.assertFalse(testimonial.is_visible) # Moderado por defeito!
        self.assertEqual(testimonial.rating, 5)
        self.assertEqual(testimonial.text, 'Serviço 5 estrelas, recomendo muito!')

    def test_invalid_rating_rejected(self):
        """Avaliações fora do intervalo de 1 a 5 devem ser rejeitadas."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            json.dumps({'rating': 6, 'text': 'Muito bom!'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(Testimonial.objects.count(), 0)

    def test_short_or_empty_text_rejected(self):
        """Testemunhos vazios ou com menos de 5 carateres devem ser rejeitados."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            json.dumps({'rating': 4, 'text': '  ok '}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(Testimonial.objects.count(), 0)

    def test_malformed_json_returns_safe_error_without_leaking_exceptions(self):
        """JSON inválido ou corrompido não deve vazar tracebacks nem exceções internas."""
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            "corrupted-non-json-data",
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertNotIn("Traceback", data.get('error', ''))
        self.assertNotIn("JSONDecodeError", data.get('error', ''))
