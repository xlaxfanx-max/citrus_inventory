from django import forms
from PIL import Image, UnidentifiedImageError

from lots.models import Color

WEEK_CHOICES = [(i, f'{i} wk' if i == 1 else f'{i} wks') for i in range(1, 9)]
DECAY_CHOICES = [(i, str(i)) for i in range(0, 11)]
BIN_CHOICES = [(i, str(i)) for i in range(1, 11)]
FIRMNESS_CHOICES = [('', 'Not checked')] + [
    (1, '1 — soft'), (2, '2 — yielding'), (3, '3 — fairly firm'),
    (4, '4 — firm'), (5, '5 — very firm'),
]


class CaptureForm(forms.Form):
    photo = forms.FileField(label='Photo of 10 fruit on the board')
    photo2 = forms.FileField(label='Second photo (optional)', required=False)
    foreman_color = forms.ChoiceField(choices=Color.choices, widget=forms.RadioSelect)
    foreman_pack_within_weeks = forms.TypedChoiceField(choices=WEEK_CHOICES, coerce=int, widget=forms.RadioSelect)
    decay_count = forms.TypedChoiceField(choices=DECAY_CHOICES, coerce=int, widget=forms.RadioSelect, initial=0)
    selection_method = forms.ChoiceField(
        choices=(
            ('across_bins', 'Random fruit across bins'),
            ('fixed_holdout', 'Fixed holdout group'),
            ('convenience', 'Convenience sample'),
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
    soft_count = forms.TypedChoiceField(choices=DECAY_CHOICES, coerce=int, required=False, initial=0)
    shrivel_count = forms.TypedChoiceField(choices=DECAY_CHOICES, coerce=int, required=False, initial=0)
    chilling_injury_count = forms.TypedChoiceField(choices=DECAY_CHOICES, coerce=int, required=False, initial=0)
    rind_breakdown_count = forms.TypedChoiceField(choices=DECAY_CHOICES, coerce=int, required=False, initial=0)
    firmness_score = forms.TypedChoiceField(
        choices=FIRMNESS_CHOICES,
        coerce=lambda value: int(value) if value else None,
        required=False,
        empty_value=None,
    )
    is_holdout = forms.BooleanField(required=False, label='This is a shelf-life holdout assessment')
    marketability = forms.ChoiceField(
        choices=(('', 'Select result'), ('pass', 'Meets pack specification'), ('fail', 'Failed pack specification')),
        required=False,
    )
    failure_reason = forms.ChoiceField(
        choices=(
            ('', 'Select limiting reason'), ('color', 'Color'), ('decay', 'Decay'),
            ('shrivel', 'Shrivel'), ('soft', 'Softness'), ('chilling', 'Chilling injury'),
            ('rind', 'Rind breakdown'), ('other', 'Other'),
        ),
        required=False,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean(self):
        data = super().clean()
        if data.get('is_holdout') and not data.get('marketability'):
            self.add_error('marketability', 'Record whether the holdout still meets specification.')
        if data.get('marketability') == 'fail' and not data.get('failure_reason'):
            self.add_error('failure_reason', 'Select the limiting reason for failure.')
        if data.get('marketability') != 'fail':
            data['failure_reason'] = ''
        return data

    def _check_image(self, f):
        if f is None:
            return f
        if f.size > 20 * 1024 * 1024:
            raise forms.ValidationError('Photo is larger than 20 MB.')
        try:
            image = Image.open(f)
            image_format = (image.format or '').upper()
            width, height = image.size
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise forms.ValidationError('The uploaded file is not a readable image.')
        finally:
            f.seek(0)
        extensions = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
        if image_format not in extensions:
            if image_format in {'HEIC', 'HEIF'}:
                raise forms.ValidationError('HEIC is not supported yet. Set the phone camera to Most Compatible (JPEG).')
            raise forms.ValidationError('Use a JPEG, PNG or WebP image.')
        if width * height > 80_000_000 or max(width, height) > 12_000:
            raise forms.ValidationError('The image dimensions are too large.')
        stem = f.name.rsplit('.', 1)[0][:180]
        f.name = f'{stem}{extensions[image_format]}'
        return f

    def clean_photo(self):
        return self._check_image(self.cleaned_data.get('photo'))

    def clean_photo2(self):
        return self._check_image(self.cleaned_data.get('photo2'))
