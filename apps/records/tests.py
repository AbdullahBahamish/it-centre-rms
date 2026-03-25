import shutil
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.accounts.bootstrap import bootstrap_roles_and_permissions
from apps.accounts.models import Role, UserProfile
from apps.core.models import SystemSettings
from .models import Category, Record, RecordAttachment
from .storage import record_attachment_path

User = get_user_model()
TEST_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "test_media"


def role(name):
    return Role.objects.get(name=name)


def force_role(user, role_name, phone_number):
    UserProfile.objects.filter(user=user).update(
        phone_number=phone_number,
        role=role(role_name),
    )
    user.refresh_from_db()
    return user


class RecordStorageTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()

    def test_record_attachment_path_uses_safe_format(self):
        record = Record.objects.create(title="Title", record_type="Case Notes")
        attachment = RecordAttachment(record=record)

        path = str(record_attachment_path(attachment, "My Scan (Final).PDF"))

        self.assertTrue(path.startswith("backup\\records\\case-notes\\") or path.startswith("backup/records/case-notes/"))
        self.assertIn(f"{record.id}", path)
        self.assertTrue(path.lower().endswith(".pdf"))
        self.assertNotIn(" ", path)


class AttachmentUploadTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TEST_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        bootstrap_roles_and_permissions()
        self._override = override_settings(MEDIA_ROOT=str(TEST_MEDIA_ROOT))
        self._override.enable()
        self.user = force_role(
            User.objects.create_user(username="owner", email="owner@example.com", password="OwnerPass123!"),
            Role.STAFF,
            "1231231234",
        )
        self.client.force_login(self.user)
        self.record = Record.objects.create(title="R1", record_type="General", created_by=self.user)

    def tearDown(self):
        self._override.disable()

    def test_upload_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile("malware.exe", b"fake", content_type="application/octet-stream")

        response = self.client.post(reverse("upload_attachment", args=[self.record.id]), {"file": upload}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported file format")
        self.assertEqual(self.record.attachments.count(), 0)

    def test_upload_accepts_supported_extension(self):
        upload = SimpleUploadedFile("report.pdf", b"%PDF-1.4\nok", content_type="application/pdf")

        response = self.client.post(reverse("upload_attachment", args=[self.record.id]), {"file": upload}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.record.attachments.count(), 1)


class AuthorizationMatrixTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.owner = force_role(User.objects.create_user(username="owner", password="OwnerPass123!", email="o@example.com"), Role.STAFF, "7000000001")
        self.contributor = force_role(User.objects.create_user(username="contributor", password="ContribPass123!", email="c@example.com"), Role.STAFF, "7000000002")
        self.other = force_role(User.objects.create_user(username="other", password="OtherPass123!", email="x@example.com"), Role.STAFF, "7000000003")
        self.admin = force_role(User.objects.create_user(username="admin", password="AdminPass123!", email="a@example.com"), Role.ADMIN, "7000000004")

        self.record = Record.objects.create(title="A", record_type="General", created_by=self.owner)
        self.record.contributors.add(self.contributor)

    def test_contributor_can_edit_record(self):
        self.client.force_login(self.contributor)
        response = self.client.get(reverse("record_update", args=[self.record.id]))
        self.assertEqual(response.status_code, 200)

    def test_non_owner_cannot_delete_record(self):
        self.client.force_login(self.contributor)
        response = self.client.post(reverse("record_delete", args=[self.record.id]))
        self.assertEqual(response.status_code, 404)

    def test_admin_can_delete_record(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("record_delete", args=[self.record.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Record.objects.filter(id=self.record.id).exists())


class ContributorSecurityTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.staff = force_role(User.objects.create_user(username="staff", password="StrongPass123!"), Role.STAFF, "7111111111")
        self.allowed = force_role(User.objects.create_user(username="allowed", password="StrongPass123!"), Role.STAFF, "7111111112")
        self.blocked = force_role(User.objects.create_user(username="blocked", password="StrongPass123!"), Role.STAFF, "7111111113")
        self.category = Category.objects.create(name="Restricted")
        self.category.allowed_users.add(self.staff, self.allowed)
        self.client.force_login(self.staff)

    def test_create_rejects_unauthorized_contributor(self):
        response = self.client.post(
            reverse("record_create"),
            {
                "title": "Restricted Ticket",
                "record_type": "General",
                "category": self.category.id,
                "contributors": [self.blocked.id],
                "case_description": "desc",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contributors must already be authorized")
        self.assertFalse(Record.objects.filter(title="Restricted Ticket").exists())


class AccessPolicyFlowTests(TestCase):
    def test_anonymous_access_returns_forbidden_without_redirect_loop(self):
        system_settings = SystemSettings.get_solo()
        system_settings.require_login = False
        system_settings.allow_anonymous_view = False
        system_settings.save()

        response = self.client.get(reverse("record_list"))

        self.assertEqual(response.status_code, 403)


class SecureFileAccessTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TEST_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        bootstrap_roles_and_permissions()
        self._override = override_settings(MEDIA_ROOT=str(TEST_MEDIA_ROOT))
        self._override.enable()
        self.owner = force_role(User.objects.create_user(username="owner", password="OwnerPass123!"), Role.STAFF, "7222222221")
        self.other = force_role(User.objects.create_user(username="other", password="OtherPass123!"), Role.STAFF, "7222222222")
        self.category = Category.objects.create(name="Owner Only")
        self.category.allowed_users.add(self.owner)
        self.record = Record.objects.create(title="A", record_type="General", created_by=self.owner, category=self.category)
        self.record.pdf_file.save("backup/records/pdfs/keep.pdf", ContentFile(b"keep"), save=True)
        self.attachment = RecordAttachment.objects.create(
            record=self.record,
            file=SimpleUploadedFile("note.txt", b"hello", content_type="text/plain"),
        )

    def tearDown(self):
        self._override.disable()

    def test_pdf_download_requires_authorized_user(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("download_record_pdf", args=[self.record.id]))
        self.assertEqual(response.status_code, 404)

    def test_attachment_download_allows_record_viewer(self):
        self.record.contributors.add(self.other)
        self.client.force_login(self.other)
        response = self.client.get(reverse("download_attachment", args=[self.attachment.id]))
        self.assertEqual(response.status_code, 200)

    def test_attachment_download_missing_file_is_hidden(self):
        self.attachment.file.delete(save=True)
        self.record.contributors.add(self.other)
        self.client.force_login(self.other)

        response = self.client.get(reverse("download_attachment", args=[self.attachment.id]))

        self.assertEqual(response.status_code, 404)


class RecordFileLifecycleTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TEST_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        bootstrap_roles_and_permissions()
        self._override = override_settings(MEDIA_ROOT=str(TEST_MEDIA_ROOT))
        self._override.enable()

    def tearDown(self):
        self._override.disable()

    def test_replacing_pdf_removes_old_file(self):
        record = Record.objects.create(title="A", record_type="General")
        record.pdf_file.save("backup/records/pdfs/old.pdf", ContentFile(b"old"), save=True)
        old_path = TEST_MEDIA_ROOT / record.pdf_file.name

        with self.captureOnCommitCallbacks(execute=True):
            record.pdf_file.save("backup/records/pdfs/new.pdf", ContentFile(b"new"), save=True)
        new_path = TEST_MEDIA_ROOT / record.pdf_file.name

        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.exists())

    def test_cleanup_orphan_files_removes_unreferenced_files(self):
        record = Record.objects.create(title="A", record_type="General")
        record.pdf_file.save("backup/records/pdfs/keep.pdf", ContentFile(b"keep"), save=True)
        kept_path = TEST_MEDIA_ROOT / record.pdf_file.name
        orphan_path = TEST_MEDIA_ROOT / "backup" / "records" / "pdfs" / "orphan.pdf"
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_bytes(b"orphan")

        call_command("cleanup_orphan_files")

        self.assertTrue(kept_path.exists())
        self.assertFalse(orphan_path.exists())
