from django import forms

from .models import Contact, Deal


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
