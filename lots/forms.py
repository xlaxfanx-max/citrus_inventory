from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.forms import modelformset_factory

from .models import ImportBatch, ModelSettings, Packout, Plant


class PackoutQualityForm(forms.ModelForm):
    """QC's direct outcome labels for one packout run, entered on the lot
    page. The carton counts stay with the Famous import; only the observed
    quality fields are editable here."""

    class Meta:
        model = Packout
        fields = ['packout_color', 'decay_pct', 'soft_pct', 'shrivel_pct', 'chilling_injury_pct', 'meets_spec', 'downgrade_reason']
        labels = {
            'packout_color': 'Observed color', 'decay_pct': 'Decay %', 'soft_pct': 'Soft %',
            'shrivel_pct': 'Shrivel %', 'chilling_injury_pct': 'Chilling injury %',
            'meets_spec': 'Met pack specification', 'downgrade_reason': 'Downgrade reason',
        }
        widgets = {
            'meets_spec': forms.NullBooleanSelect,
            'downgrade_reason': forms.TextInput(attrs={'placeholder': 'Color, decay, size, market…'}),
        }


class ImportForm(forms.Form):
    kind = forms.ChoiceField(choices=ImportBatch.Kind.choices, label='File type')
    file = forms.FileField(label='CSV file')

    def clean_file(self):
        f = self.cleaned_data['file']
        if f.size > 20 * 1024 * 1024:
            raise forms.ValidationError('File is larger than 20 MB.')
        return f


class ModelSettingsForm(forms.ModelForm):
    class Meta:
        model = ModelSettings
        fields = [
            'cci_dg_max', 'cci_lg_max', 'cci_s_max',
            'prior_drift_dg', 'prior_drift_lg', 'prior_drift_s', 'prior_drift_y',
            'start_cci_dg', 'start_cci_lg', 'start_cci_s', 'start_cci_y',
            'buffer_days', 'decay_flag_pct', 'min_fruit_for_score', 'max_horizon_days',
            'sample_overdue_days', 'import_gap_days',
            'sample_fruit_count', 'warm_storage_temp_c', 'warm_weeks_flag', 'temperature_response',
            'color_correction_method',
        ]

    def clean(self):
        data = super().clean()
        dg, lg, s = data.get('cci_dg_max'), data.get('cci_lg_max'), data.get('cci_s_max')
        if None not in (dg, lg, s) and not (dg < lg < s):
            raise forms.ValidationError('Thresholds must increase: dark green max < light green max < silver max.')
        return data


class PlantSettingsForm(forms.ModelForm):
    """Plant capacity plus the report recipients, edited as one text box and
    stored as PlantReportRecipient rows."""

    report_recipients = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text="Comma-separated email addresses that receive this plant's Monday report.",
    )

    class Meta:
        model = Plant
        fields = ['weekly_pack_capacity_bins']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial.setdefault('report_recipients', ', '.join(self.instance.recipient_list))

    def clean_report_recipients(self):
        emails = Plant.split_recipients(self.cleaned_data['report_recipients'])
        invalid = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid.append(email)
        if invalid:
            raise ValidationError(f'Invalid email address(es): {", ".join(invalid)}')
        return emails

    def save(self, commit=True):
        plant = super().save(commit=commit)
        if commit:
            plant.set_recipients(self.cleaned_data['report_recipients'])
        return plant


PlantRecipientsFormSet = modelformset_factory(Plant, form=PlantSettingsForm, extra=0)
