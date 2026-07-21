import shutil
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django import forms

from apps.accounts.bootstrap import bootstrap_roles_and_permissions
from apps.accounts.models import Role, UserProfile
from apps.core.models import SystemSettings
from .models import Category, ITAsset, Record, RecordAttachment, RecordType
from .presentation.forms import RecordForm
from .storage import record_attachment_path

User = get_user_model()
TEST_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "test_media"


def role(name):
    return Role.objects.get(name=name)


def record_type(name="General"):
    return RecordType.objects.get_or_create(name=name)[0]


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
        record = Record.objects.create(title="Title", record_type=record_type("Case Notes"))
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
        self.record = Record.objects.create(title="R1", record_type=record_type(), created_by=self.user)

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

        self.record = Record.objects.create(title="A", record_type=record_type(), created_by=self.owner)
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
                "record_type": record_type().name,
                "category": self.category.id,
                "contributors": f"[{self.blocked.id}]",
                "case_description": "desc",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
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
        self.record = Record.objects.create(title="A", record_type=record_type(), created_by=self.owner, category=self.category)
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
        record = Record.objects.create(title="A", record_type=record_type())
        record.pdf_file.save("backup/records/pdfs/old.pdf", ContentFile(b"old"), save=True)
        old_path = TEST_MEDIA_ROOT / record.pdf_file.name

        with self.captureOnCommitCallbacks(execute=True):
            record.pdf_file.save("backup/records/pdfs/new.pdf", ContentFile(b"new"), save=True)
        new_path = TEST_MEDIA_ROOT / record.pdf_file.name

        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.exists())

    def test_cleanup_orphan_files_removes_unreferenced_files(self):
        record = Record.objects.create(title="A", record_type=record_type())
        record.pdf_file.save("backup/records/pdfs/keep.pdf", ContentFile(b"keep"), save=True)
        kept_path = TEST_MEDIA_ROOT / record.pdf_file.name
        orphan_path = TEST_MEDIA_ROOT / "backup" / "records" / "pdfs" / "orphan.pdf"
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_bytes(b"orphan")

        call_command("cleanup_orphan_files")

        self.assertTrue(kept_path.exists())
        self.assertFalse(orphan_path.exists())


class RecordFormContributorFilteringTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.staff = force_role(User.objects.create_user(username="staff", password="StrongPass123!"), Role.STAFF, "7333333331")
        self.allowed = force_role(User.objects.create_user(username="allowed", password="StrongPass123!"), Role.STAFF, "7333333332")
        self.blocked = force_role(User.objects.create_user(username="blocked", password="StrongPass123!"), Role.STAFF, "7333333333")
        self.manager = force_role(User.objects.create_user(username="manager", password="StrongPass123!"), Role.MANAGER, "7333333334")
        self.admin = force_role(User.objects.create_user(username="admin", password="StrongPass123!"), Role.ADMIN, "7333333335")
        self.category = Category.objects.create(name="Scoped")
        self.category.allowed_users.add(self.staff, self.allowed)
        self.record_type = record_type()

    def test_form_limits_contributors_to_selected_category_plus_privileged_roles(self):
        form = RecordForm(
            initial={"category": self.category.id, "record_type": self.record_type.name},
            categories=[self.category],
            record_types=[self.record_type],
        )

        contributors = [user.username for user in form.allowed_contributors]

        self.assertEqual(contributors, ["admin", "allowed", "manager", "staff"])

    def test_allow_all_contributors_exposes_full_active_queryset(self):
        form = RecordForm(
            initial={
                "category": self.category.id,
                "record_type": self.record_type.name,
                "allow_all_contributors": True,
            },
            categories=[self.category],
            record_types=[self.record_type],
        )

        contributors = [user.username for user in form.allowed_contributors]

        self.assertEqual(contributors, ["admin", "allowed", "blocked", "manager", "staff"])

    def test_contributors_field_uses_hidden_input_for_chip_picker(self):
        form = RecordForm(
            initial={"category": self.category.id, "record_type": self.record_type.name},
            categories=[self.category],
            record_types=[self.record_type],
        )

        self.assertIsInstance(form.fields["contributors"].widget, forms.HiddenInput)
        self.assertEqual(form.initial["contributors"], "[]")

    def test_retention_field_uses_native_date_input(self):
        form = RecordForm(
            initial={"category": self.category.id, "record_type": self.record_type.name},
            categories=[self.category],
            record_types=[self.record_type],
        )

        self.assertEqual(form.fields["retention_until"].widget.input_type, "date")

    def test_create_record_accepts_blocked_contributor_when_override_enabled(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("record_create"),
            {
                "title": "Override Ticket",
                "record_type": self.record_type.name,
                "category": self.category.id,
                "allow_all_contributors": "on",
                "contributors": f"[{self.blocked.id}]",
                "case_description": "desc",
            },
        )

        self.assertEqual(response.status_code, 302)
        record = Record.objects.get(title="Override Ticket")
        self.assertTrue(record.allow_all_contributors)
        self.assertEqual(list(record.contributors.values_list("username", flat=True)), ["blocked"])

    def test_create_record_persists_multiple_selected_contributors(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("record_create"),
            {
                "title": "Team Ticket",
                "record_type": self.record_type.name,
                "category": self.category.id,
                "contributors": f"[{self.allowed.id}, {self.staff.id}]",
                "case_description": "desc",
            },
        )

        self.assertEqual(response.status_code, 302)
        record = Record.objects.get(title="Team Ticket")
        self.assertEqual(
            list(record.contributors.order_by("username").values_list("username", flat=True)),
            ["allowed", "staff"],
        )

    def test_record_form_template_renders_maintenance_workflow_without_contributor_picker(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("record_create"))

        self.assertContains(response, "Device Information")
        self.assertContains(response, "Maintenance Details")
        self.assertContains(response, "Technical Report")
        self.assertContains(response, "Completion")
        self.assertContains(response, 'name="contributors"')
        self.assertNotContains(response, 'class="contributors-picker"')
        self.assertNotContains(response, 'name="contributors" class="form-control"')

    def test_contributor_options_are_grouped_by_category_for_live_filtering(self):
        form = RecordForm(
            initial={"category": self.category.id, "record_type": self.record_type.name},
            categories=[self.category],
            record_types=[self.record_type],
        )

        category_options = form.contributor_options["byCategory"][str(self.category.id)]
        usernames = [user["username"] for user in category_options]

        self.assertEqual(usernames, ["admin", "allowed", "manager", "staff"])
        self.assertIn({"id": self.blocked.id, "username": "blocked"}, form.contributor_options["all"])

    def test_create_record_persists_asset_and_maintenance_fields(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("record_create"),
            {
                "title": "Laptop keyboard repair",
                "record_type": self.record_type.name,
                "category": self.category.id,
                "asset_tag": "it-1001",
                "device_type": "laptop",
                "manufacturer": "dell",
                "model": "Latitude 5440",
                "serial_number": "SN1001",
                "operating_system": "windows_11",
                "system_architecture": "x64",
                "cpu": "Intel Core i5",
                "ram": "16 GB",
                "storage": "512 GB SSD",
                "location": "Maintenance Room",
                "department": "IT Centre",
                "room": "MR-01",
                "device_owner": "Faculty Lab",
                "maintenance_type": "hardware_repair",
                "problem_category": "Keyboard",
                "priority": "high",
                "reported_by": "Lab coordinator",
                "assigned_technician": self.allowed.id,
                "assistant_technician": self.staff.id,
                "support_team": "Maintenance Room",
                "date_received": "2026-07-13",
                "expected_completion_date": "2026-07-15",
                "maintenance_status": "diagnosing",
                "case_description": "Keyboard keys are not responding.",
                "diagnosis": "Keyboard membrane failure.",
                "repair_performed": "Replaced keyboard module.",
                "software_installed": "Dell Command Update",
                "drivers_installed": "Keyboard hotkey driver",
                "parts_replaced": "Keyboard assembly",
                "bios_updated": "on",
                "firmware_updated": "on",
                "testing_results": "Keyboard passed function test.",
                "remarks": "Return to user after burn-in.",
                "completed_by": self.allowed.id,
                "completion_date": "2026-07-14",
                "final_device_status": "working",
            },
        )

        self.assertEqual(response.status_code, 302)
        record = Record.objects.select_related("asset", "assigned_technician", "assistant_technician").get(title="Laptop keyboard repair")
        self.assertEqual(record.asset.asset_tag, "IT-1001")
        self.assertEqual(record.asset.device_type, "laptop")
        self.assertEqual(record.priority, "high")
        self.assertEqual(record.maintenance_status, "diagnosing")
        self.assertEqual(record.assigned_technician, self.allowed)
        self.assertEqual(record.assistant_technician, self.staff)
        self.assertEqual(list(record.contributors.order_by("username").values_list("username", flat=True)), ["allowed", "staff"])
        self.assertEqual(ITAsset.objects.count(), 1)

    def test_expected_completion_date_cannot_precede_received_date(self):
        form = RecordForm(
            data={
                "title": "Invalid schedule",
                "record_type": self.record_type.name,
                "category": self.category.id,
                "date_received": "2026-07-13",
                "expected_completion_date": "2026-07-12",
                "contributors": "[]",
            },
            categories=[self.category],
            record_types=[self.record_type],
        )

        self.assertFalse(form.is_valid())
        self.assertIn("expected_completion_date", form.errors)
