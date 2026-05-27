from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Contact, Deal, DealActivity


class DealModelTests(TestCase):
    def test_creating_deal_records_initial_history(self):
        deal = Deal.objects.create(name="Acme Expansion", company="Acme")

        activity = deal.activities.get()

        self.assertEqual(activity.entry_type, DealActivity.EntryType.STAGE_CHANGE)
        self.assertIn("Deal created in Lead.", activity.content)

    def test_changing_stage_records_history(self):
        deal = Deal.objects.create(name="Northwind Trial", company="Northwind")

        deal.stage = Deal.Stage.WON
        deal.save()

        stage_entries = deal.activities.filter(
            entry_type=DealActivity.EntryType.STAGE_CHANGE
        )
        self.assertEqual(stage_entries.count(), 2)
        self.assertIn("Stage changed from Lead to Won.", stage_entries.last().content)


class DealViewTests(TestCase):
    def setUp(self):
        self.deal = Deal.objects.create(
            name="Globex Pilot",
            company="Globex",
            stage=Deal.Stage.FREE_TRIAL,
        )
        self.contact = Contact.objects.create(
            first_name="Casey",
            last_name="Nguyen",
            company="Globex",
            email="casey@example.com",
        )

    def test_pipeline_view_renders_deal(self):
        response = self.client.get(reverse("crm:pipeline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Globex Pilot")

    def test_table_view_renders_deal(self):
        response = self.client.get(reverse("crm:deal-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Globex")

    def test_add_contact_to_deal(self):
        response = self.client.post(
            reverse("crm:deal-add-contact", args=[self.deal.pk]),
            {"existing_contact": self.contact.pk},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.deal.contacts.filter(pk=self.contact.pk).exists())

    def test_add_note_to_deal(self):
        response = self.client.post(
            reverse("crm:deal-add-note", args=[self.deal.pk]),
            {"content": "Sent the onboarding checklist."},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            self.deal.activities.filter(content__icontains="onboarding checklist").exists()
        )


class ContactImportTests(TestCase):
    def test_contact_page_shows_sample_import_format(self):
        response = self.client.get(reverse("crm:contact-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bulk import contacts")
        self.assertContains(
            response,
            "first_name,last_name,job_title,company,email,phone",
        )

    def test_import_contacts_from_csv(self):
        csv_file = SimpleUploadedFile(
            "contacts.csv",
            (
                b"first_name,last_name,job_title,company,email,phone\n"
                b"Ava,Patel,Head of Sales,Acme,ava@example.com,+61 400 000 000\n"
                b"Luca,Rossi,Founder,Northwind,luca@example.com,+61 411 111 111\n"
            ),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("crm:contact-import"),
            {"csv_file": csv_file},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contact.objects.count(), 2)
        self.assertTrue(Contact.objects.filter(email="ava@example.com").exists())
        self.assertContains(response, "Imported 2 contact(s).")

    def test_import_rejects_missing_required_header(self):
        csv_file = SimpleUploadedFile(
            "contacts.csv",
            b"last_name,job_title,company,email,phone\nPatel,Head of Sales,Acme,ava@example.com,+61 400 000 000\n",
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("crm:contact-import"),
            {"csv_file": csv_file},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contact.objects.count(), 0)
        self.assertContains(response, "Missing required column(s): first_name.")
