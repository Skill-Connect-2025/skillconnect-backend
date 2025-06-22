from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.apps import apps
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender='jobs.Job')
def invalidate_job_matches(sender, instance, **kwargs):
    """Invalidate MatchResult entries when a Job is updated."""
    try:
        MatchResult = apps.get_model('recommendations', 'MatchResult')
        MatchResult.objects.filter(job=instance).delete()
        logger.info(f"Invalidated MatchResult for job {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating MatchResult for job {instance.id}: {str(e)}")

@receiver(post_save, sender='users.Worker')
def invalidate_worker_matches(sender, instance, **kwargs):
    """Invalidate MatchResult entries when a Worker is updated."""
    try:
        MatchResult = apps.get_model('recommendations', 'MatchResult')
        MatchResult.objects.filter(worker=instance).delete()
        logger.info(f"Invalidated MatchResult for worker {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating MatchResult for worker {instance.id}: {str(e)}")

@receiver(post_save, sender='users.Education')
def invalidate_worker_education_matches(sender, instance, **kwargs):
    """Invalidate MatchResult entries when Worker education is updated."""
    try:
        MatchResult = apps.get_model('recommendations', 'MatchResult')
        MatchResult.objects.filter(worker=instance.worker).delete()
        logger.info(f"Invalidated MatchResult for worker {instance.worker.id} due to education change")
    except Exception as e:
        logger.error(f"Error invalidating MatchResult for worker {instance.worker.id}: {str(e)}")


try:
    Worker = apps.get_model('users', 'Worker')
    target_jobs_field = Worker._meta.get_field('target_jobs')
    if target_jobs_field.many_to_many:
        @receiver(m2m_changed, sender=target_jobs_field.remote_field.through)
        def invalidate_worker_target_jobs_matches(sender, instance, action, **kwargs):
            """Invalidate MatchResult entries when Worker target jobs change."""
            if action in ['post_add', 'post_remove', 'post_clear']:
                try:
                    MatchResult = apps.get_model('recommendations', 'MatchResult')
                    MatchResult.objects.filter(worker=instance).delete()
                    logger.info(f"Invalidated MatchResult for worker {instance.id} due to target_jobs M2M change")
                except Exception as e:
                    logger.error(f"Error invalidating MatchResult for worker {instance.id}: {str(e)}")
except Exception as e:
    logger.warning(f"Could not set up m2m_changed signal for Worker.target_jobs: {str(e)}")