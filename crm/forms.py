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


class ContactImportForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV file",
        help_text="Use UTF-8 CSV with the sample header shown below.",
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        return csv_file


class DealNoteForm(forms.Form):
    content = forms.CharField(
        label="New note",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Add the latest update..."}),
    )


class AddContactToDealForm(forms.Form):
    existing_contact = forms.ModelChoiceField(
        queryset=Contact.objects.none(),
        label="Link an existing contact",
    )

    def __init__(self, *args, deal: Deal, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Contact.objects.exclude(pk__in=deal.contacts.values_list("pk", flat=True))
        self.fields["existing_contact"].queryset = queryset
        self.has_choices = queryset.exists()
