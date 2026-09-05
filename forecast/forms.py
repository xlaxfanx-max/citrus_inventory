from django import forms

from .models import PlanDecision


class PlanDecisionForm(forms.ModelForm):
    """One decision on one recommendation. Model.clean enforces the
    reason / planned-date rules so the same checks apply in the admin."""

    class Meta:
        model = PlanDecision
        fields = ['status', 'reason', 'planned_pack_date', 'notes']
        widgets = {
            'planned_pack_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, recommendation=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.recommendation = recommendation
        self.instance.decided_by = user
        self.fields['reason'].required = False
        self.fields['planned_pack_date'].required = False
