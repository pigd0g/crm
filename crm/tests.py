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
