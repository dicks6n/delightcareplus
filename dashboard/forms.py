from django import forms
from django.forms import inlineformset_factory

from blog.models import Post
from cart.models import Coupon, DeliveryZone
from catalog.models import Brand, Category, Department, Product, Variant
from core.models import Banner, SiteSettings, Testimonial


class StyledMixin:
    """Adds the dashboard input classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            elif isinstance(w, forms.ClearableFileInput):
                w.attrs.setdefault("class", "form-control")
                w.attrs.setdefault("accept", "image/*")
            else:
                w.attrs.setdefault("class", "form-control")
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 4)


class ProductForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name", "brand", "category", "form", "sku", "size_label", "weight_grams",
            "short_description", "description", "benefits", "ingredients", "how_to_use", "skin_type",
            "price", "compare_price", "stock", "image",
            "is_active", "is_featured", "is_best_seller", "is_new",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "benefits": forms.Textarea(attrs={"rows": 4, "placeholder": "One benefit per line"}),
            "ingredients": forms.Textarea(attrs={"rows": 3}),
            "how_to_use": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        data = super().clean()
        price, compare = data.get("price"), data.get("compare_price")
        if price is not None and price <= 0:
            self.add_error("price", "Price must be more than 0.")
        if compare and price and compare <= price:
            self.add_error("compare_price", "The old price should be higher than the price (or leave it empty).")
        return data


class VariantForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Variant
        fields = ["label", "price", "compare_price", "stock", "sort_order"]


VariantFormSet = inlineformset_factory(Product, Variant, form=VariantForm, extra=1, can_delete=True)


class BrandForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "country", "country_code", "tagline", "story", "logo", "banner", "accent_color", "is_featured", "sort_order"]
        widgets = {"accent_color": forms.TextInput(attrs={"type": "color"})}


class DepartmentForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "icon", "description", "image", "sort_order", "is_active"]


class CategoryForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["department", "name", "icon", "description", "image", "sort_order", "is_active"]


class CouponForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ["code", "description", "discount_type", "value", "min_order_amount", "max_uses",
                  "valid_from", "valid_until", "is_active"]
        widgets = {
            "valid_from": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "valid_until": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }


class DeliveryZoneForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = DeliveryZone
        fields = ["name", "towns", "pickup_stations", "pickup_fee", "home_fee", "extra_kg_fee", "delivery_days", "sort_order", "is_active"]
        widgets = {"towns": forms.Textarea(attrs={"rows": 6}), "pickup_stations": forms.Textarea(attrs={"rows": 4})}


class BannerForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Banner
        fields = ["title", "subtitle", "button_text", "link", "image", "sort_order", "is_active"]


class TestimonialForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ["name", "location", "quote", "rating", "is_active"]


class PostForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "topic", "excerpt", "body", "cover", "related_products", "is_published", "published_at"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 14}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "related_products": forms.SelectMultiple(attrs={"size": 8}),
        }


class SiteSettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        exclude = ["updated_at"]


class ImportForm(forms.Form):
    csv_file = forms.FileField(help_text="CSV saved from Excel/Google Sheets")
    images_zip = forms.FileField(required=False, help_text="Optional: a .zip of photos named as in the image column")
    update_existing = forms.BooleanField(required=False, initial=True,
                                         help_text="If a product with the same name + brand exists, update it")
