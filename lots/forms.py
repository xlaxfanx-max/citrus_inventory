from django import forms
from django.forms import modelformset_factory

from .models import ImportBatch, ModelSettings, Plant


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
        ]

    def clean(self):
        data = super().clean()
        dg, lg, s = data.get('cci_dg_max'), data.get('cci_lg_max'), data.get('cci_s_max')
        if None not in (dg, lg, s) and not (dg < lg < s):
            raise forms.ValidationError('Thresholds must increase: dark green max < light green max < silver max.')
        return data


PlantRecipientsFormSet = modelformset_factory(
    Plant,
    fields=['report_recipients', 'weekly_pack_capacity_bins'],
    extra=0,
)
