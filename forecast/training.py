"""Build point-in-time training rows without leaking future observations."""

from .features import features_for_lot


TRAINING_COLUMNS = [
    'plant_code', 'lot_no', 'as_of_date', 'days_in_storage', 'variety',
    'grower_id', 'block', 'receiving_color', 'harvest_to_receive_days',
    'intake_cci_mean', 'intake_cci_std', 'sample_cci_mean', 'sample_cci_p10',
    'sample_cci_median', 'sample_cci_p90', 'sample_cci_std', 'selection_method',
    'sampled_bins_count', 'decay_count', 'soft_count', 'shrivel_count',
    'chilling_injury_count', 'rind_breakdown_count', 'firmness_score',
    'temperature_f_mean', 'temperature_f_min', 'temperature_f_max',
    'humidity_pct_mean', 'ethylene_ppm_max', 'co2_pct_max',
    'environment_reading_count', 'environment_day_coverage_pct',
    'treatment_count', 'treatment_types',
    'final_packout_date', 'days_to_final_packout', 'packout_color',
    'packout_decay_pct', 'packout_soft_pct', 'packout_shrivel_pct',
    'packout_chilling_injury_pct', 'packout_meets_spec', 'fresh_pct',
    'first_holdout_failure_date', 'days_to_holdout_failure',
    'holdout_failure_reason',
]


def _value(summary, key):
    return summary.get(key) if summary else None


def rows_for_lot(lot):
    """One feature snapshot per sample; future information appears only in label columns."""
    samples = list(lot.samples.filter(is_void=False).prefetch_related('photos').order_by('sampled_at', 'id'))
    packout = lot.packouts.filter(is_final=True).order_by('packed_date', 'id').first()
    holdout_failure = next(
        (
            sample for sample in samples
            if sample.purpose == sample.Purpose.HOLDOUT
            and sample.marketability == sample.Marketability.FAIL
        ),
        None,
    )
    rows = []
    for sample in samples:
        as_of = sample.sampled_on
        if packout and as_of > packout.packed_date:
            continue
        if holdout_failure and as_of > holdout_failure.sampled_on:
            # Once the holdout has failed, later observations are outside its
            # marketable-life risk set and would teach the model from fruit that
            # was already known to be unmarketable.
            continue
        features = features_for_lot(lot, as_of)
        environment = features['environment']
        treatments = features['treatments']
        distribution = sample.cci_distribution or {}
        rows.append({
            'plant_code': lot.plant.code,
            'lot_no': lot.lot_no,
            'as_of_date': as_of.isoformat(),
            'days_in_storage': (as_of - lot.receive_date).days,
            'variety': lot.variety,
            'grower_id': lot.grower_id,
            'block': lot.block,
            'receiving_color': lot.receiving_color,
            'harvest_to_receive_days': features['harvest_to_receive_days'],
            'intake_cci_mean': lot.intake_cci_mean,
            'intake_cci_std': lot.intake_cci_std,
            'sample_cci_mean': distribution.get('mean'),
            'sample_cci_p10': distribution.get('p10'),
            'sample_cci_median': distribution.get('median'),
            'sample_cci_p90': distribution.get('p90'),
            'sample_cci_std': distribution.get('std'),
            'selection_method': sample.selection_method,
            'sampled_bins_count': sample.sampled_bins_count,
            'decay_count': sample.decay_count,
            'soft_count': sample.soft_count,
            'shrivel_count': sample.shrivel_count,
            'chilling_injury_count': sample.chilling_injury_count,
            'rind_breakdown_count': sample.rind_breakdown_count,
            'firmness_score': sample.firmness_score,
            'temperature_f_mean': _value(environment['temperature_f'], 'mean'),
            'temperature_f_min': _value(environment['temperature_f'], 'min'),
            'temperature_f_max': _value(environment['temperature_f'], 'max'),
            'humidity_pct_mean': _value(environment['relative_humidity_pct'], 'mean'),
            'ethylene_ppm_max': _value(environment['ethylene_ppm'], 'max'),
            'co2_pct_max': _value(environment['co2_pct'], 'max'),
            'environment_reading_count': environment['reading_count'],
            'environment_day_coverage_pct': environment['day_coverage_pct'],
            'treatment_count': len(treatments),
            'treatment_types': ';'.join(sorted({event['type'] for event in treatments})),
            'final_packout_date': packout.packed_date.isoformat() if packout else '',
            'days_to_final_packout': (packout.packed_date - as_of).days if packout else None,
            'packout_color': packout.packout_color if packout else '',
            'packout_decay_pct': packout.decay_pct if packout else None,
            'packout_soft_pct': packout.soft_pct if packout else None,
            'packout_shrivel_pct': packout.shrivel_pct if packout else None,
            'packout_chilling_injury_pct': packout.chilling_injury_pct if packout else None,
            'packout_meets_spec': packout.meets_spec if packout else None,
            'fresh_pct': packout.fresh_pct if packout else None,
            'first_holdout_failure_date': (
                holdout_failure.sampled_on.isoformat() if holdout_failure else ''
            ),
            'days_to_holdout_failure': (
                (holdout_failure.sampled_on - as_of).days
                if holdout_failure and holdout_failure.sampled_on >= as_of else None
            ),
            'holdout_failure_reason': (
                holdout_failure.failure_reason
                if holdout_failure and holdout_failure.sampled_on >= as_of else ''
            ),
        })
    return rows


def training_rows(lots):
    for lot in lots:
        yield from rows_for_lot(lot)
