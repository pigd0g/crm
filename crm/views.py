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
    DEAL_CONTACT_IMPORT_HEADERS,
    AddContactToDealForm,
    ContactForm,
    ContactImportForm,
    DealContactImportForm,
    DealForm,
    DealNoteForm,
)
from .models import Contact, Deal, DealActivity


def parse_uploaded_csv(uploaded_file):
    try:
        csv_text = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("The CSV file must be UTF-8 encoded.") from error

    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("The CSV file is empty.")

    headers = [field.strip() for field in reader.fieldnames]
    return headers, reader


def normalize_csv_row(row):
    return {
        key.strip(): (value or "").strip()
        for key, value in row.items()
        if key is not None
    }


def format_form_errors(form):
    errors = []
    for field, field_errors in form.errors.items():
        field_name = field if field != "__all__" else "row"
        errors.append(f"{field_name}: {' '.join(field_errors)}")
    return "; ".join(errors)


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
        queryset = (
            Deal.objects.prefetch_related("contacts")
            .annotate(contact_count=Count("contacts"))
            .order_by("company", "name")
        )
        valid_stages = {value for value, _ in Deal.Stage.choices}
        self.selected_stage = self.request.GET.get("stage", "")
        if self.selected_stage in valid_stages:
            queryset = queryset.filter(stage=self.selected_stage)
        else:
            self.selected_stage = ""
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stage_options"] = Deal.Stage.choices
        context["selected_stage"] = self.selected_stage
        return context


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


class DealDeleteView(generic.View):
    def post(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        deal_name = deal.name
        deal.delete()
        messages.success(request, f'Deal "{deal_name}" deleted.')
        return redirect("crm:deal-list")


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


class ImportPageView(generic.TemplateView):
    template_name = "crm/import_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contact_import_form"] = kwargs.get("contact_import_form", ContactImportForm())
        context["deal_contact_import_form"] = kwargs.get(
            "deal_contact_import_form",
            DealContactImportForm(),
        )
        context["contact_sample_import_header"] = ",".join(CONTACT_IMPORT_HEADERS)
        context["contact_sample_import_row"] = (
            "Ava,Patel,Head of Sales,Acme,ava.patel@example.com,+61 400 000 000"
        )
        context["deal_contact_sample_import_header"] = ",".join(DEAL_CONTACT_IMPORT_HEADERS)
        context["deal_contact_sample_import_row"] = (
            "Northwind Trial,Northwind,free_trial,15000.00,2026-06-15,"
            "Priority expansion opportunity.,Ava,Patel,Head of Sales,Northwind,"
            "ava@example.com,+61 400 000 000"
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


class ContactDeleteView(generic.View):
    def post(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        contact_name = contact.full_name
        contact.delete()
        messages.success(request, f'Contact "{contact_name}" deleted.')
        return redirect("crm:contact-list")


class ContactImportView(generic.View):
    def post(self, request):
        form = ContactImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Import failed. Upload a valid CSV file.")
            return self._render_import_page(request, form)

        try:
            imported_count = self._import_contacts(form.cleaned_data["csv_file"])
        except ValueError as error:
            messages.error(request, f"Import failed. {error}")
            return self._render_import_page(request, form)

        messages.success(request, f"Imported {imported_count} contact(s).")
        return redirect("crm:import-page")

    def _render_import_page(self, request, form):
        view = ImportPageView()
        view.setup(request)
        context = view.get_context_data(contact_import_form=form)
        return view.render_to_response(context)

    def _import_contacts(self, uploaded_file):
        headers, reader = parse_uploaded_csv(uploaded_file)
        missing_headers = [
            header for header in CONTACT_IMPORT_HEADERS if header not in headers
        ]
        if missing_headers:
            missing = ", ".join(missing_headers)
            raise ValueError(f"Missing required column(s): {missing}.")

        contacts = []
        for line_number, row in enumerate(reader, start=2):
            normalized_row = normalize_csv_row(row)
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


class DealContactImportView(generic.View):
    def post(self, request):
        form = DealContactImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Import failed. Upload a valid CSV file.")
            return self._render_import_page(request, form)

        try:
            deal_count, contact_count = self._import_deals_and_contacts(
                form.cleaned_data["csv_file"]
            )
        except ValueError as error:
            messages.error(request, f"Import failed. {error}")
            return self._render_import_page(request, form)

        messages.success(
            request,
            f"Imported {deal_count} deal(s) and {contact_count} contact(s).",
        )
        return redirect("crm:import-page")

    def _render_import_page(self, request, form):
        view = ImportPageView()
        view.setup(request)
        context = view.get_context_data(deal_contact_import_form=form)
        return view.render_to_response(context)

    def _import_deals_and_contacts(self, uploaded_file):
        headers, reader = parse_uploaded_csv(uploaded_file)
        missing_headers = [
            header for header in DEAL_CONTACT_IMPORT_HEADERS if header not in headers
        ]
        if missing_headers:
            missing = ", ".join(missing_headers)
            raise ValueError(f"Missing required column(s): {missing}.")

        deal_count = 0
        contact_count = 0
        with transaction.atomic():
            for line_number, row in enumerate(reader, start=2):
                normalized_row = normalize_csv_row(row)
                if not any(normalized_row.values()):
                    continue

                deal_form = DealForm(
                    {
                        "name": normalized_row["deal_name"],
                        "company": normalized_row["deal_company"],
                        "stage": normalized_row["deal_stage"] or Deal.Stage.LEAD,
                        "value": normalized_row["deal_value"],
                        "expected_close_date": normalized_row["deal_expected_close_date"],
                        "description": normalized_row["deal_description"],
                    }
                )
                if not deal_form.is_valid():
                    raise ValueError(
                        f"Row {line_number} has invalid deal data: {format_form_errors(deal_form)}."
                    )

                deal = deal_form.save()
                deal_count += 1

                raw_contact_values = {
                    "first_name": normalized_row["contact_first_name"],
                    "last_name": normalized_row["contact_last_name"],
                    "job_title": normalized_row["contact_job_title"],
                    "company": normalized_row["contact_company"],
                    "email": normalized_row["contact_email"],
                    "phone": normalized_row["contact_phone"],
                }
                if not any(raw_contact_values.values()):
                    continue

                if not raw_contact_values["first_name"]:
                    raise ValueError(f"Row {line_number} is missing contact_first_name.")

                contact_values = {
                    **raw_contact_values,
                    "company": raw_contact_values["company"] or normalized_row["deal_company"],
                }
                contact_form = ContactForm(contact_values)
                if not contact_form.is_valid():
                    raise ValueError(
                        f"Row {line_number} has invalid contact data: {format_form_errors(contact_form)}."
                    )

                contact = contact_form.save()
                deal.contacts.add(contact)
                contact_count += 1

        if not deal_count:
            raise ValueError("The CSV file does not contain any import rows.")

        return deal_count, contact_count


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
            error = form.errors.get("existing_contact", ["Contact could not be linked."])[0]
            messages.error(request, error)
        return HttpResponseRedirect(reverse("crm:deal-detail", args=[deal.pk]))


class DealRemoveContactView(generic.View):
    def post(self, request, pk, contact_pk):
        deal = get_object_or_404(Deal, pk=pk)
        contact = get_object_or_404(Contact, pk=contact_pk)
        deal.contacts.remove(contact)
        messages.success(request, "Contact removed from the deal.")
        return HttpResponseRedirect(reverse("crm:deal-detail", args=[deal.pk]))
