from django import forms
from django.conf import settings

from orders.mpesa import format_phone

from .models import Campaign, CampaignUpdate


class DonateForm(forms.Form):
    amount = forms.IntegerField(max_value=1_000_000)
    name = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=20, required=False)
    email = forms.EmailField(required=False)
    message = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    is_anonymous = forms.BooleanField(required=False)
    method = forms.ChoiceField(choices=(("mpesa", "M-Pesa"), ("airtel", "Airtel Money")), initial="mpesa")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < settings.FOUNDATION_MIN_DONATION:
            raise forms.ValidationError(f"The smallest donation is KES {settings.FOUNDATION_MIN_DONATION}.")
        return amount

    def clean(self):
        data = super().clean()
        if data.get("method") == "mpesa":
            phone = format_phone(data.get("phone", ""))
            if not phone:
                self.add_error("phone", "Enter the Safaricom number to send the M-Pesa prompt to, e.g. 0712 345 678.")
            data["phone"] = phone
        else:
            data["phone"] = format_phone(data.get("phone", "")) or data.get("phone", "")
        return data


class CampaignForm(forms.ModelForm):
    """What members of the public fill in to start a fundraiser. Staff review it before it goes live."""
    agree = forms.BooleanField(label="I confirm this story is true and I can share documents (e.g. medical or school bills) if the Foundation asks.")

    class Meta:
        model = Campaign
        fields = ["title", "category", "beneficiary", "location", "goal", "end_date", "summary", "story",
                  "cover", "video_url", "organiser_phone"]
        labels = {"organiser_phone": "Your phone (so we can contact you)", "goal": "Goal (KES)"}
        widgets = {"story": forms.Textarea(attrs={"rows": 9}), "summary": forms.Textarea(attrs={"rows": 2}),
                   "end_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organiser_phone"].required = True
        self.fields["goal"].min_value = 1000
        self.fields["goal"].widget.attrs["min"] = 1000

    def clean_organiser_phone(self):
        phone = format_phone(self.cleaned_data["organiser_phone"])
        if not phone:
            raise forms.ValidationError("Enter a Kenyan mobile number, e.g. 0712 345 678.")
        return phone

    def clean_goal(self):
        goal = self.cleaned_data["goal"]
        if goal < 1000:
            raise forms.ValidationError("Set a goal of at least KES 1,000.")
        return goal


class UpdateForm(forms.ModelForm):
    class Meta:
        model = CampaignUpdate
        fields = ["title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}
