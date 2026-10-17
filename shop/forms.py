import re

from django import forms

from .models import ShopSettings

HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
DOMAIN = re.compile(r'^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


class ShopSettingsForm(forms.ModelForm):
    remove_hero_image = forms.BooleanField(required=False, label='Remove banner image')

    class Meta:
        model = ShopSettings
        exclude = ['company', 'updated_at']
        widgets = {
            'about_text': forms.Textarea(attrs={'rows': 4}),
            'brand_color': forms.TextInput(attrs={'type': 'color'}),
        }

    def clean_brand_color(self):
        v = (self.cleaned_data.get('brand_color') or '').strip()
        if not HEX.match(v):
            raise forms.ValidationError('Use a colour like #0f766e.')
        return v

    def clean_hero_image(self):
        img = self.cleaned_data.get('hero_image')
        if img and hasattr(img, 'size') and img.size > 3 * 1024 * 1024:
            raise forms.ValidationError('Image is too large (max 3 MB).')
        return img

    def clean_domain(self):
        v = (self.cleaned_data.get('domain') or '').strip().lower()
        v = re.sub(r'^https?://', '', v).split('/')[0].split(':')[0]
        if v.startswith('www.'):
            v = v[4:]
        if not v:
            return None          # unique + null: একাধিক কোম্পানির ফাঁকা ডোমেইন সমস্যা করে না
        if not DOMAIN.match(v):
            raise forms.ValidationError('Enter a domain like shop.example.com.')
        return v

    def clean_whatsapp(self):
        return re.sub(r'\D', '', self.cleaned_data.get('whatsapp') or '')

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get('remove_hero_image') and not self.files.get('hero_image'):
            obj.hero_image = None
        if commit:
            obj.save()
        return obj
