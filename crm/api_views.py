import json
from decimal import Decimal

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .forms import ContactForm, DealForm
from .models import Contact, Deal, DealActivity

CONTACT_FIELDS = ["first_name", "last_name", "job_title", "company", "email", "phone"]
DEAL_FIELDS = ["name", "company", "stage", "value", "expected_close_date", "description"]


def json_error(message, *, status=400, errors=None):
    payload = {"error": message}
    if errors:
        payload["details"] = errors
    return JsonResponse(payload, status=status)


def parse_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Request body must be valid UTF-8 JSON.")


def normalize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is None:
        return ""
    return value


def build_form_data(payload, fields, instance=None):
    unknown_fields = sorted(set(payload.keys()) - set(fields))
    if unknown_fields:
        unknown = ", ".join(unknown_fields)
        raise ValueError(f"Unknown field(s): {unknown}.")

    data = {}
    for field in fields:
        if field in payload:
            data[field] = payload[field]
        elif instance is not None:
            data[field] = normalize_value(getattr(instance, field))
        else:
            data[field] = ""
    return data


def serialize_contact(contact):
    return {
        "id": contact.pk,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "full_name": contact.full_name,
        "job_title": contact.job_title,
        "company": contact.company,
        "email": contact.email,
        "phone": contact.phone,
        "deal_ids": list(contact.deals.values_list("id", flat=True)),
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
    }


def serialize_activity(activity):
    return {
        "id": activity.pk,
        "entry_type": activity.entry_type,
        "entry_type_label": activity.get_entry_type_display(),
        "content": activity.content,
        "created_at": activity.created_at.isoformat(),
    }


def serialize_deal(deal):
    contacts = list(deal.contacts.all())
    activities = list(deal.activities.all())
    return {
        "id": deal.pk,
        "name": deal.name,
        "company": deal.company,
        "stage": deal.stage,
        "stage_label": deal.get_stage_display(),
        "value": str(deal.value) if deal.value is not None else None,
        "expected_close_date": (
            deal.expected_close_date.isoformat() if deal.expected_close_date else None
        ),
        "description": deal.description,
        "contact_ids": [contact.pk for contact in contacts],
        "contacts": [serialize_contact(contact) for contact in contacts],
        "activities": [serialize_activity(activity) for activity in activities],
        "created_at": deal.created_at.isoformat(),
        "updated_at": deal.updated_at.isoformat(),
    }


@method_decorator(csrf_exempt, name="dispatch")
class ApiView(View):
    def parse_request_json(self, request):
        try:
            return parse_json(request)
        except ValueError as error:
            return json_error(str(error))

    def form_error_response(self, form):
        return json_error("Validation failed.", errors=form.errors, status=400)


class StageListApiView(ApiView):
    def get(self, request):
        return JsonResponse(
            {
                "stages": [
                    {"value": value, "label": label}
                    for value, label in Deal.Stage.choices
                ]
            }
        )


class ContactListApiView(ApiView):
    def get(self, request):
        contacts = Contact.objects.order_by("company", "last_name", "first_name")
        return JsonResponse({"contacts": [serialize_contact(contact) for contact in contacts]})

    def post(self, request):
        payload = self.parse_request_json(request)
        if isinstance(payload, JsonResponse):
            return payload

        try:
            form_data = build_form_data(payload, CONTACT_FIELDS)
        except ValueError as error:
            return json_error(str(error))

        form = ContactForm(form_data)
        if not form.is_valid():
            return self.form_error_response(form)

        contact = form.save()
        return JsonResponse(serialize_contact(contact), status=201)


class ContactDetailApiView(ApiView):
    def get(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        return JsonResponse(serialize_contact(contact))

    def patch(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        payload = self.parse_request_json(request)
        if isinstance(payload, JsonResponse):
            return payload

        if not payload:
            return json_error("Provide at least one field to update.")

        try:
            form_data = build_form_data(payload, CONTACT_FIELDS, instance=contact)
        except ValueError as error:
            return json_error(str(error))

        form = ContactForm(form_data, instance=contact)
        if not form.is_valid():
            return self.form_error_response(form)

        contact = form.save()
        return JsonResponse(serialize_contact(contact))

    def delete(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk)
        contact.delete()
        return HttpResponse(status=204)


class DealListApiView(ApiView):
    def get(self, request):
        deals = Deal.objects.prefetch_related("contacts", "activities").order_by("company", "name")
        return JsonResponse({"deals": [serialize_deal(deal) for deal in deals]})

    def post(self, request):
        payload = self.parse_request_json(request)
        if isinstance(payload, JsonResponse):
            return payload

        try:
            form_data = build_form_data(payload, DEAL_FIELDS)
        except ValueError as error:
            return json_error(str(error))

        form = DealForm(form_data)
        if not form.is_valid():
            return self.form_error_response(form)

        deal = form.save()
        return JsonResponse(serialize_deal(deal), status=201)


class DealDetailApiView(ApiView):
    def get(self, request, pk):
        deal = get_object_or_404(Deal.objects.prefetch_related("contacts", "activities"), pk=pk)
        return JsonResponse(serialize_deal(deal))

    def patch(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        payload = self.parse_request_json(request)
        if isinstance(payload, JsonResponse):
            return payload

        if not payload:
            return json_error("Provide at least one field to update.")

        try:
            form_data = build_form_data(payload, DEAL_FIELDS, instance=deal)
        except ValueError as error:
            return json_error(str(error))

        form = DealForm(form_data, instance=deal)
        if not form.is_valid():
            return self.form_error_response(form)

        deal = form.save()
        deal.refresh_from_db()
        return JsonResponse(serialize_deal(deal))

    def delete(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        deal.delete()
        return HttpResponse(status=204)


class DealNoteApiView(ApiView):
    def post(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        payload = self.parse_request_json(request)
        if isinstance(payload, JsonResponse):
            return payload

        content = str(payload.get("content", "")).strip()
        if not content:
            return json_error("content is required.")

        activity = DealActivity.objects.create(
            deal=deal,
            entry_type=DealActivity.EntryType.NOTE,
            content=content,
        )
        return JsonResponse(serialize_activity(activity), status=201)


class DealContactLinkApiView(ApiView):
    def post(self, request, pk):
        deal = get_object_or_404(Deal, pk=pk)
        payload = self.parse_request_json(request)
        if isinstance(payload, JsonResponse):
            return payload

        contact_id = payload.get("contact_id")
        if contact_id in (None, ""):
            return json_error("contact_id is required.")

        contact = get_object_or_404(Contact, pk=contact_id)
        deal.contacts.add(contact)
        deal.refresh_from_db()
        return JsonResponse(serialize_deal(deal))


class DealContactDetailApiView(ApiView):
    def delete(self, request, pk, contact_pk):
        deal = get_object_or_404(Deal, pk=pk)
        contact = get_object_or_404(Contact, pk=contact_pk)
        deal.contacts.remove(contact)
        return HttpResponse(status=204)
