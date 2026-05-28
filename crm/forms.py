from django import forms

from .models import Contact, Deal

CONTACT_IMPORT_HEADERS = [
    "first_name",
    "last_name",
    "job_title",
    "company",
    "email",
    "phone",
]

DEAL_CONTACT_IMPORT_HEADERS = [
    "deal_name",
    "deal_company",
    "deal_stage",
    "deal_value",
    "deal_expected_close_date",
    "deal_description",
    "contact_first_name",
    "contact_last_name",
    "contact_job_title",
    "contact_company",
    "contact_email",
    "contact_phone",
]


class DateInput(forms.DateInput):
    input_type = "date"


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = ["name", "company", "stage", "value", "expected_close_date", "description"]
        widgets = {
            "expected_close_date": DateInput(),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "job_title", "company", "email", "phone"]


class CsvImportForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file",
        help_text="Use UTF-8 CSV with the sample header shown below.",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        return csv_file


class ContactImportForm(CsvImportForm):
    pass


class DealContactImportForm(CsvImportForm):
    csv_file = forms.FileField(
        label="Deals and contacts CSV file",
        help_text="Use one deal and one optional contact per row in a UTF-8 CSV file.",
    )


class DealNoteForm(forms.Form):
    content = forms.CharField(
        label="New note",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Add the latest update..."}),
    )


class AddContactToDealForm(forms.Form):
    existing_contact = forms.ModelChoiceField(
        queryset=Contact.objects.none(),
        label="Link an existing contact",
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, deal: Deal, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Contact.objects.exclude(pk__in=deal.contacts.values_list("pk", flat=True)).order_by(
            "company", "last_name", "first_name"
        )
        self.fields["existing_contact"].queryset = queryset
        self.has_choices = queryset.exists()
        self.contact_options = [
            {"id": contact.pk, "label": self.build_contact_label(contact)}
            for contact in queryset
        ]

    @staticmethod
    def build_contact_label(contact: Contact) -> str:
        details = [contact.company, contact.email, contact.phone]
        detail_text = " - ".join(detail for detail in details if detail)
        return f"{contact.full_name} - {detail_text}" if detail_text else contact.full_name
