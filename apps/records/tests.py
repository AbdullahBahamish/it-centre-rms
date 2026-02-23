import shutil
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings

from .models import Record, RecordAttachment
from .services import RecordService
from .storage import record_attachment_path

TEST_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "test_media"


class RecordServiceTests(TestCase):
    def test_create_record_normalizes_text_fields(self):
        record = RecordService.create_record(
            title="  Network   outage  report  ",
            record_type="  Incident   Log ",
            created_by=None,
            case_description="  First line.\nSecond line.  ",
        )

        self.assertEqual(record.title, "Network outage report")
        self.assertEqual(record.record_type, "Incident Log")
        self.assertEqual(record.case_description, "First line.\nSecond line.")


class RecordStorageTests(TestCase):
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
        self._override = override_settings(MEDIA_ROOT=str(TEST_MEDIA_ROOT))
        self._override.enable()
        self.record = Record.objects.create(title="R1", record_type="General")

    def tearDown(self):
        self._override.disable()

    def test_upload_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile("malware.exe", b"fake", content_type="application/octet-stream")

        response = self.client.post(
            reverse("upload_attachment", args=[self.record.id]),
            {"file": upload},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported file format")
        self.assertEqual(self.record.attachments.count(), 0)

    def test_upload_rejects_file_too_large(self):
        upload = SimpleUploadedFile("big.pdf", b"x" * (10 * 1024 * 1024 + 1), content_type="application/pdf")

        response = self.client.post(
            reverse("upload_attachment", args=[self.record.id]),
            {"file": upload},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "File is too large")
        self.assertEqual(self.record.attachments.count(), 0)

    def test_upload_accepts_supported_extension(self):
        upload = SimpleUploadedFile("report.pdf", b"ok", content_type="application/pdf")

        response = self.client.post(
            reverse("upload_attachment", args=[self.record.id]),
            {"file": upload},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.record.attachments.count(), 1)
