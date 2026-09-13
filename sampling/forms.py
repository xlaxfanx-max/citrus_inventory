from django import forms
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from lots.models import Color
from .models import BoardCalibration

WEEK_CHOICES = [(0, _('Today'))] + [(i, format_lazy(_('{n} wk') if i == 1 else _('{n} wks'), n=i)) for i in range(1, 9)]
BIN_CHOICES = [(i, str(i)) for i in range(1, 11)]
FIRMNESS_CHOICES = [('', _('Not checked'))] + [
    (1, _('1 — soft')), (2, _('2 — yielding')), (3, _('3 — fairly firm')),
    (4, _('4 — firm')), (5, _('5 — very firm')),
]


class CaptureForm(forms.Form):
    """The foreman's weekly check. `fruit_count` is the number of fruit
    inspected for defects (25 by default, the USDA lemon inspection minimum);
    the photo always shows ten of them. When decay meets the flag percent the
    foreman is asked to inspect a second set and record the combined count
    out of twice the base number."""

    calibration = forms.ModelChoiceField(queryset=BoardCalibration.objects.none(), required=False,
        empty_label=_('Uncalibrated / demonstration'), label=_('Sampling station'))
    photo = forms.FileField(label=_('Photo of 10 fruit on the board'))
    photo2 = forms.FileField(label=_('Second photo (optional)'), required=False)
    foreman_color = forms.ChoiceField(choices=Color.choices, widget=forms.RadioSelect)
    foreman_pack_within_weeks = forms.TypedChoiceField(choices=WEEK_CHOICES, coerce=int, widget=forms.RadioSelect)
    fruit_count = forms.TypedChoiceField(choices=(), coerce=int, widget=forms.RadioSelect, required=False)
    decay_count = forms.IntegerField(min_value=0, initial=0)
    selection_method = forms.ChoiceField(
        choices=(
            ('across_bins', _('Random fruit across bins')),
            ('fixed_holdout', _('Fixed holdout group')),
            ('convenience', _('Convenience sample')),
        ),
        required=False,
        initial='across_bins',
    )
    sampled_bins_count = forms.TypedChoiceField(
        choices=BIN_CHOICES,
        coerce=int,
        required=False,
        initial=1,
    )
    soft_count = forms.IntegerField(min_value=0, required=False, initial=0)
    shrivel_count = forms.IntegerField(min_value=0, required=False, initial=0)
    chilling_injury_count = forms.IntegerField(min_value=0, required=False, initial=0)
    rind_breakdown_count = forms.IntegerField(min_value=0, required=False, initial=0)
    firmness_score = forms.TypedChoiceField(
        choices=FIRMNESS_CHOICES,
        coerce=lambda value: int(value) if value else None,
        required=False,
        empty_value=None,
    )
    is_holdout = forms.BooleanField(required=False, label=_('This is a shelf-life holdout assessment'))
    marketability = forms.ChoiceField(
        choices=(('', _('Select result')), ('pass', _('Meets pack specification')), ('fail', _('Failed pack specification'))),
        required=False,
    )
    failure_reason = forms.ChoiceField(
        choices=(
            ('', _('Select limiting reason')), ('color', _('Color')), ('decay', _('Decay')),
            ('shrivel', _('Shrivel')), ('soft', _('Softness')), ('chilling', _('Chilling injury')),
            ('rind', _('Rind breakdown')), ('other', _('Other')),
        ),
        required=False,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))
    opened_at = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, plant=None, fruit_count=25, **kwargs):
        super().__init__(*args, **kwargs)
        if plant is not None:
            self.fields['calibration'].queryset = BoardCalibration.objects.filter(plant=plant, active=True)
        self.base_fruit_count = int(fruit_count)
        self.double_fruit_count = 2 * self.base_fruit_count
        self.fields['fruit_count'].choices = [
            (self.base_fruit_count, _('%(n)d fruit') % {'n': self.base_fruit_count}),
            (self.double_fruit_count, _('%(n)d fruit (doubled sample)') % {'n': self.double_fruit_count}),
        ]
        self.fields['fruit_count'].initial = self.base_fruit_count

    def clean(self):
        data = super().clean()
        fruit_count = data.get('fruit_count') or self.base_fruit_count
        for field in ('decay_count', 'soft_count', 'shrivel_count', 'chilling_injury_count', 'rind_breakdown_count'):
            value = data.get(field)
            if value is not None and value > fruit_count:
                self.add_error(field, _('Cannot exceed the %(n)d fruit inspected.') % {'n': fruit_count})
        if data.get('is_holdout') and not data.get('marketability'):
            self.add_error('marketability', _('Record whether the holdout still meets specification.'))
        if data.get('marketability') == 'fail' and not data.get('failure_reason'):
            self.add_error('failure_reason', _('Select the limiting reason for failure.'))
        if data.get('marketability') != 'fail':
            data['failure_reason'] = ''
        return data

    def _check_image(self, f):
        if f is None:
            return f
        if f.size > 20 * 1024 * 1024:
            raise forms.ValidationError(_('Photo is larger than 20 MB.'))
        try:
            image = Image.open(f)
            image_format = (image.format or '').upper()
            width, height = image.size
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise forms.ValidationError(_('The uploaded file is not a readable image.'))
        finally:
            f.seek(0)
        extensions = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
        if image_format not in extensions:
            if image_format in {'HEIC', 'HEIF'}:
                raise forms.ValidationError(_('HEIC is not supported yet. Set the phone camera to Most Compatible (JPEG).'))
            raise forms.ValidationError(_('Use a JPEG, PNG or WebP image.'))
        if width * height > 80_000_000 or max(width, height) > 12_000:
            raise forms.ValidationError(_('The image dimensions are too large.'))
        stem = f.name.rsplit('.', 1)[0][:180]
        f.name = f'{stem}{extensions[image_format]}'
        return f

    def clean_photo(self):
        return self._check_image(self.cleaned_data.get('photo'))

    def clean_photo2(self):
        return self._check_image(self.cleaned_data.get('photo2'))
