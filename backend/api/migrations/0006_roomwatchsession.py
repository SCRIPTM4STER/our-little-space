from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_roominvitation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomWatchSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video_url', models.URLField(blank=True, default='', max_length=500)),
                ('is_playing', models.BooleanField(default=False)),
                ('position', models.FloatField(default=0.0)),
                ('playback_rate', models.FloatField(default=1.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('controller', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='controlled_watch_sessions', to=settings.AUTH_USER_MODEL)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_watch_sessions', to=settings.AUTH_USER_MODEL)),
                ('room', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='watch_session', to='api.room')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
