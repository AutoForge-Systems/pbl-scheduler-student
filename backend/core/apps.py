from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core'

    def ready(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from django.core.management import call_command
        import threading

        def reset_job():
            call_command('reset_scheduling_data', '--yes')

        scheduler = BackgroundScheduler()
        scheduler.add_job(reset_job, 'cron', hour=19, minute=0)
        threading.Thread(target=scheduler.start, daemon=True).start()
