from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_user_university_roll_number"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="is_available_for_booking",
        ),
    ]
