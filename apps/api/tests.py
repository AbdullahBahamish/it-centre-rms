from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.bootstrap import bootstrap_roles_and_permissions
from apps.accounts.models import Role, UserProfile
from apps.records.models import Category, Record, RecordType


User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class ApiSecurityAndCrudTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.client = APIClient()
        self.user = User.objects.create_user("api-staff", password="StrongPass123!")
        UserProfile.objects.filter(user=self.user).update(role=Role.objects.get(name=Role.STAFF))
        self.user.refresh_from_db()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.record_type = RecordType.objects.create(name="API Test")
        self.category = Category.objects.create(name="API Category")

    def test_api_requires_authentication(self):
        self.client.credentials()

        response = self.client.get("/api/v1/records/")

        self.assertEqual(response.status_code, 401)

    def test_login_and_me_return_authenticated_identity(self):
        self.client.credentials()

        login = self.client.post("/api/v1/auth/login/", {"username": "api-staff", "password": "StrongPass123!"}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "api-staff")

    def test_staff_can_create_and_read_owned_record(self):
        payload = {
            "title": "API-created record",
            "record_type": self.record_type.name,
            "category": self.category.id,
            "case_description": "Created through integration API",
        }

        created = self.client.post("/api/v1/records/", payload, format="json")

        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["created_by"]["username"], "api-staff")
        self.assertTrue(Record.objects.get(pk=created.data["id"]).pdf_file.name)
        listed = self.client.get("/api/v1/records/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)

    def test_viewer_cannot_create_records(self):
        UserProfile.objects.filter(user=self.user).update(role=Role.objects.get(name=Role.VIEWER))

        response = self.client.post(
            "/api/v1/records/",
            {"title": "Denied", "record_type": self.record_type.name, "category": self.category.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_logout_revokes_token(self):
        response = self.client.post("/api/v1/auth/logout/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

    def test_partial_update_preserves_existing_record_values(self):
        created = self.client.post(
            "/api/v1/records/",
            {"title": "Original title", "record_type": self.record_type.name, "category": self.category.id,
             "case_description": "Keep this description"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)

        updated = self.client.patch(
            f"/api/v1/records/{created.data['id']}/",
            {"title": "Updated title"},
            format="json",
        )

        self.assertEqual(updated.status_code, 200)
        record = Record.objects.get(pk=created.data["id"])
        self.assertEqual(record.title, "Updated title")
        self.assertEqual(record.case_description, "Keep this description")

    @override_settings(API_TOKEN_TTL_SECONDS=1)
    def test_expired_token_is_rejected(self):
        self.token.created = timezone.now() - timedelta(seconds=10)
        self.token.save(update_fields=["created"])

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 401)
