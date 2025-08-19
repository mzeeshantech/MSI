
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('cnic', models.CharField(max_length=15, unique=True)),
                ('job_title', models.CharField(max_length=100)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
            ],
        ),
    ]
