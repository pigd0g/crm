import csv
from io import StringIO

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import generic

from .forms import (
    CONTACT_IMPORT_HEADERS,
    AddContactToDealForm,
    ContactForm,
    ContactImportForm,
    DealForm,
    DealNoteForm,
)
from .models import Contact, Deal, DealActivity


def stage_columns():
    deals = (
        Deal.objects.prefetch_related("contacts")
        .annotate(contact_count=Count("contacts"))
        .order_by("-updated_at")
    )
    grouped = {stage: [] for stage, _ in Deal.Stage.choices}
    for deal in deals:
        grouped[deal.stage].append(deal)

    return [
        {"value": stage, "label": label, "deals": grouped[stage]}
        for stage, label in Deal.Stage.choices
    ]


class HomeRedirectView(generic.RedirectView):
    pattern_name = "crm:pipeline"


class PipelineView(generic.TemplateView):
    template_name = "crm/pipeline.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["columns"] = stage_columns()
        context["deal_total"] = Deal.objects.count()
        context["won_value"] = (
            Deal.objects.filter(stage=Deal.Stage.WON).aggregate(total=Sum("value"))["total"]
            or 0
        )
        return context


class DealListView(generic.ListView):
    model = Deal
    template_name = "crm/deal_list.html"
    context_object_name = "deals"

    def get_queryset(self):
        return (
            Deal.objects.prefetch_related("contacts")
            .annotate(contact_count=Count("contacts"))
            .order_by("company", "name")
        )


class DealCreateView(generic.CreateView):
    model = Deal
    form_class = DealForm
    template_name = "crm/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "New deal"
        context["subtitle"] = "Capture a new opportunity and add contacts afterward."
        return context

    def form_valid(self, form):
        messages.success(self.request, "Deal created.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("crm:deal-detail", args=[self.object.pk])


class DealUpdateView(generic.UpdateView):
    model = Deal
    form_class = DealForm
    template_name = "crm/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit deal"
        context["subtitle"] = "Update the current deal details and stage."
        return context

    def form_valid(self, form):
        messages.success(self.request, "Deal updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("crm:deal-detail", args=[self.object.pk])


class DealDetailView(generic.DetailView):
    model = Deal
    template_name = "crm/deal_detail.html"
    context_object_name = "deal"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deal = self.object
        add_contact_form = AddContactToDealForm(deal=deal)
        context["activities"] = deal.activities.select_related("deal")
        context["note_form"] = DealNoteForm()
        context["add_contact_form"] = add_contact_form
        context["has_available_contacts"] = add_contact_form.has_choices
        return context


class ContactListView(generic.ListView):
    model = Contact
    template_name = "crm/contact_list.html"
    context_object_name = "contacts"

    def get_queryset(self):
        return Contact.objects.annotate(deal_count=Count("deals"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["import_form"] = kwargs.get("import_form", ContactImportForm())
        context["sample_import_header"] = ",".join(CONTACT_IMPORT_HEADERS)
        context["sample_import_row"] = (
            "Ava,Patel,Head of Sales,Acme,ava.patel@example.com,+61 400 000 000"
        )
        return context


class ContactCreateView(generic.CreateView):
    model = Contact
    form_class = ContactForm
    template_name = "crm/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "New contact"
        context["subtitle"] = "Add a contact to the CRM directory."
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        deal_id = self.request.GET.get("deal") or self.request.POST.get("deal")
        if deal_id:
            deal = get_object_or_404(Deal, pk=deal_id)
            deal.contacts.add(self.object)
            messages.success(self.request, "Contact created and linked to the deal.")
            return redirect("crm:deal-detail", pk=deal.pk)

        messages.success(self.request, "Contact created.")
        return response

    def get_success_url(self):
        return reverse("crm:contact-list")

    def get_initial(self):
        initial = super().get_initial()
        deal_id = self.request.GET.get("deal")
        if deal_id:
            deal = Deal.objects.filter(pk=deal_id).first()
            if deal:
                initial["company"] = deal.company
        return initial


class ContactUpdateView(generic.UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = "crm/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit contact"
        context["subtitle"] = "Keep contact details current."
        return context

    def form_valid(self, form):
        messages.success(self.request, "Contact updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("crm:contact-list")


class ContactImportView(generic.View):
    def post(self, request):
        form = ContactImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Import failed. Upload a valid CSV file.")
            return self._render_contact_list_with_form(request, form)

        try:
            imported_count = self._import_contacts(form.cleaned_data["csv_file"])
        except ValueError as error:
            messages.error(request, f"Import failed. {error}")
            return self._render_contact_list_with_form(request, form)

        messages.success(request, f"Imported {imported_count} contact(s).")
        return redirect("crm:contact-list")

    def _render_contact_list_with_form(self, request, form):
        view = ContactListView()
        view.setup(request)
        view.object_list = view.get_queryset()
        context = view.get_context_data(import_form=form)
        return view.render_to_response(context)

    def _import_contacts(self, uploaded_file):
        try:
            csv_text = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("The CSV file must be UTF-8 encoded.") from error

        reader = csv.DictReader(StringIO(csv_text))
        if reader.fieldnames is None:
            raise ValueError("The CSV file is empty.")

        headers = [field.strip() for field in reader.fieldnames]
        missing_headers = [
            header for header in CONTACT_IMPORT_HEADERS if header not in headers
        ]
        if missing_headers:
            missing = ", ".join(missing_headers)
            raise ValueError(f"Missing required column(s): {missing}.")

        contacts = []
        for line_number, row in enumerate(reader, start=2):
            normalized_row = {
                key.strip(): (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            if not any(normalized_row.values()):
                continue

            first_name = normalized_row["first_name"]
            if not first_name:
                raise ValueError(f"Row {line_number} is missing first_name.")

            contacts.append(
                Contact(
                    first_name=first_name,
                    last_name=normalized_row["last_name"],
                    job_title=normalized_row["job_title"],
                    company=normalized_row["company"],
                    email=normalized_row["email"],
                    phone=normalized_row["phone"],
                )
            )

        if not contacts:
            raise ValueError("The CSV file does not contain any contact rows.")

        with transaction.atomic():
            Contact.objects.bulk_create(contacts)

        return len(contacts)


class DealAddNoteView(generic.View):
    def post(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        form = DealNoteForm(request.POST)
        if form.is_valid():
            DealActivity.objects.create(
                deal=deal,
                entry_type=DealActivity.EntryType.NOTE,
                content=form.cleaned_data["content"],
            )
            messages.success(request, "Note added.")
        else:
            messages.error(request, "Note could not be added.")
        return HttpResponseRedirect(reverse("crm:deal-detail", args=[deal.pk]))


class DealAddContactView(generic.View):
    def post(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        form = AddContactToDealForm(request.POST, deal=deal)
        if form.is_valid():
            deal.contacts.add(form.cleaned_data["existing_contact"])
            messages.success(request, "Contact linked to the deal.")
        else:
            messages.error(request, "Contact could not be linked.")
        return HttpResponseRedirect(reverse("crm:deal-detail", args=[deal.pk]))


class DealRemoveContactView(generic.View):
    def post(self, request, pk, contact_pk):
        deal = get_object_or_404(Deal, pk=pk)
        contact = get_object_or_404(Contact, pk=contact_pk)
        deal.contacts.remove(contact)
        messages.success(request, "Contact removed from the deal.")
        return HttpResponseRedirect(reverse("crm:deal-detail", args=[deal.pk]))
