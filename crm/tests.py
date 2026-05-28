from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import AddContactToDealForm, DEAL_CONTACT_IMPORT_HEADERS
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

    def test_deal_list_can_filter_by_stage(self):
        Deal.objects.create(name="Won Expansion", company="Acme", stage=Deal.Stage.WON)

        response = self.client.get(reverse("crm:deal-list"), {"stage": Deal.Stage.WON})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Won Expansion")
        self.assertNotContains(response, "Globex Pilot")

    def test_add_contact_to_deal(self):
        response = self.client.post(
            reverse("crm:deal-add-contact", args=[self.deal.pk]),
            {"existing_contact": self.contact.pk},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.deal.contacts.filter(pk=self.contact.pk).exists())

    def test_deal_detail_renders_searchable_contact_options(self):
        other_contact = Contact.objects.create(
            first_name="Ava",
            last_name="Patel",
            company="Northwind",
            email="ava@example.com",
        )

        response = self.client.get(reverse("crm:deal-detail", args=[self.deal.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'list="available-contacts"', html=False)
        self.assertContains(
            response,
            AddContactToDealForm.build_contact_label(other_contact),
        )

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

    def test_delete_deal_from_web(self):
        response = self.client.post(
            reverse("crm:deal-delete", args=[self.deal.pk]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Deal.objects.filter(pk=self.deal.pk).exists())


class ImportViewTests(TestCase):
    def test_import_page_shows_both_sample_import_formats(self):
        response = self.client.get(reverse("crm:import-page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bulk import contacts")
        self.assertContains(
            response,
            "first_name,last_name,job_title,company,email,phone",
        )
        self.assertContains(response, "Bulk import deals and contacts")
        self.assertContains(response, ",".join(DEAL_CONTACT_IMPORT_HEADERS))

    def test_contact_page_no_longer_shows_bulk_import_ui(self):
        response = self.client.get(reverse("crm:contact-list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Bulk import contacts")
        self.assertContains(response, "Contact information")

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

    def test_import_deals_and_contacts_from_csv(self):
        csv_file = SimpleUploadedFile(
            "deals-and-contacts.csv",
            (
                b"deal_name,deal_company,deal_stage,deal_value,deal_expected_close_date,deal_description,"
                b"contact_first_name,contact_last_name,contact_job_title,contact_company,contact_email,contact_phone\n"
                b"Northwind Trial,Northwind,free_trial,15000.00,2026-06-15,Priority expansion opportunity.,"
                b"Ava,Patel,Head of Sales,Northwind,ava@example.com,+61 400 000 000\n"
            ),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("crm:deal-contact-import"),
            {"csv_file": csv_file},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Deal.objects.count(), 1)
        self.assertEqual(Contact.objects.count(), 1)
        deal = Deal.objects.get()
        contact = Contact.objects.get()
        self.assertTrue(deal.contacts.filter(pk=contact.pk).exists())
        self.assertContains(response, "Imported 1 deal(s) and 1 contact(s).")

    def test_import_deals_without_contact_from_csv(self):
        csv_file = SimpleUploadedFile(
            "deals.csv",
            (
                b"deal_name,deal_company,deal_stage,deal_value,deal_expected_close_date,deal_description,"
                b"contact_first_name,contact_last_name,contact_job_title,contact_company,contact_email,contact_phone\n"
                b"Globex Expansion,Globex,lead,8000.00,2026-07-01,Initial discovery call scheduled.,,,,,,\n"
            ),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("crm:deal-contact-import"),
            {"csv_file": csv_file},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Deal.objects.count(), 1)
        self.assertEqual(Contact.objects.count(), 0)
        self.assertEqual(Deal.objects.get().contacts.count(), 0)
        self.assertContains(response, "Imported 1 deal(s) and 0 contact(s).")

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

    def test_delete_contact_from_web(self):
        contact = Contact.objects.create(
            first_name="Ava",
            last_name="Patel",
            company="Acme",
            email="ava@example.com",
        )

        response = self.client.post(
            reverse("crm:contact-delete", args=[contact.pk]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contact.objects.filter(pk=contact.pk).exists())


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

    def test_delete_contact_api(self):
        response = self.client.delete(
            reverse("crm_api:contact-detail", args=[self.contact.pk]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Contact.objects.filter(pk=self.contact.pk).exists())

    def test_delete_deal_api(self):
        response = self.client.delete(
            reverse("crm_api:deal-detail", args=[self.deal.pk]),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Deal.objects.filter(pk=self.deal.pk).exists())
