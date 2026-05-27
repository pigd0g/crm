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


class ApiTests(TestCase):
    def setUp(self):
        self.contact = Contact.objects.create(
            first_name="Ava",
            last_name="Patel",
            company="Acme",
            email="ava@example.com",
        )
        self.deal = Deal.objects.create(
            name="Northwind Trial",
            company="Northwind",
            stage=Deal.Stage.FREE_TRIAL,
        )

    def test_list_stages(self):
        response = self.client.get(reverse("crm_api:stage-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stages"][0]["value"], "lead")

    def test_create_contact_api(self):
        response = self.client.post(
            reverse("crm_api:contact-list"),
            data='{"first_name":"Luca","last_name":"Rossi","company":"Globex","email":"luca@example.com"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["first_name"], "Luca")
        self.assertTrue(Contact.objects.filter(email="luca@example.com").exists())

    def test_patch_deal_api_creates_stage_history(self):
        response = self.client.patch(
            reverse("crm_api:deal-detail", args=[self.deal.pk]),
            data='{"stage":"won","value":"18000.00"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, Deal.Stage.WON)
        self.assertEqual(response.json()["stage"], "won")
        self.assertTrue(
            self.deal.activities.filter(content__icontains="Stage changed from Free trial to Won.").exists()
        )

    def test_add_note_api(self):
        response = self.client.post(
            reverse("crm_api:deal-add-note", args=[self.deal.pk]),
            data='{"content":"Customer requested pricing."}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["entry_type"], "note")
        self.assertTrue(
            self.deal.activities.filter(content__icontains="requested pricing").exists()
        )

    def test_link_and_remove_contact_api(self):
        link_response = self.client.post(
            reverse("crm_api:deal-add-contact", args=[self.deal.pk]),
            data=f'{{"contact_id": {self.contact.pk}}}',
            content_type="application/json",
        )

        self.assertEqual(link_response.status_code, 200)
        self.assertTrue(self.deal.contacts.filter(pk=self.contact.pk).exists())

        unlink_response = self.client.delete(
            reverse("crm_api:deal-remove-contact", args=[self.deal.pk, self.contact.pk]),
        )

        self.assertEqual(unlink_response.status_code, 204)
        self.assertFalse(self.deal.contacts.filter(pk=self.contact.pk).exists())

    def test_api_rejects_unknown_fields(self):
        response = self.client.post(
            reverse("crm_api:contact-list"),
            data='{"first_name":"Ava","nickname":"Ace"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Unknown field(s): nickname.")
