from django.db import migrations


def backfill(apps, schema_editor):
    SamplePhoto = apps.get_model('sampling', 'SamplePhoto')
    FruitMeasurement = apps.get_model('sampling', 'FruitMeasurement')
    rows = []
    for photo in SamplePhoto.objects.filter(status='scored').iterator():
        labs = list(photo.per_fruit_lab or [])
        ccis = list(photo.per_fruit_cci or [])
        for index in range(max(len(labs), len(ccis))):
            lab = labs[index] if index < len(labs) and isinstance(labs[index], (list, tuple)) and len(labs[index]) == 3 else (None, None, None)
            rows.append(FruitMeasurement(
                photo=photo, index=index, lab_l=lab[0], lab_a=lab[1], lab_b=lab[2],
                cci=ccis[index] if index < len(ccis) else None,
            ))
    FruitMeasurement.objects.bulk_create(rows, batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [
        ('sampling', '0007_fruitmeasurement'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
