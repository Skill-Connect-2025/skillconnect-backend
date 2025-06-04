from apps.users.models import Worker
from apps.jobs.models import Job, Feedback, ClientFeedback
from .models import Embedding
import logging
from difflib import SequenceMatcher
import re
import json
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg


logger = logging.getLogger(__name__)

class MatchEngine:
    SKILL_WEIGHT = 0.4
    TARGET_JOB_WEIGHT = 0.2
    EXPERIENCE_WEIGHT = 0.2
    EDUCATION_WEIGHT = 0.1
    LOCATION_WEIGHT = 0.1

    @staticmethod
    def normalize_string(s):
        """Normalize strings for comparison."""
        return re.sub(r'\s+', ' ', s.lower().strip())

    @staticmethod
    def calculate_skill_match(job_skills, worker_skills):
        job_skill_set = set(skill.lower().strip() for skill in job_skills.split(','))
        worker_skill_set = set(skill.name.lower() for skill in worker_skills.all())
        if not job_skill_set:
            return 0.0
        common_skills = job_skill_set.intersection(worker_skill_set)
        return len(common_skills) / len(job_skill_set)

    @staticmethod
    def calculate_experience_score(worker):
        if not worker.has_experience:
            return 0.0
        return min(worker.years_of_experience / 5, 1.0)  # Cap at 5 years

    @staticmethod
    def calculate_rating_score(worker):
        # Calculate average rating from both worker and client feedback
        worker_rating = Feedback.objects.filter(worker=worker).aggregate(Avg('rating'))['rating__avg'] or 0
        client_rating = ClientFeedback.objects.filter(worker=worker).aggregate(Avg('rating'))['rating__avg'] or 0
        
        # If both ratings exist, take average; otherwise use available rating
        if worker_rating and client_rating:
            return (worker_rating + client_rating) / 10  # Normalize to 0-1
        elif worker_rating:
            return worker_rating / 5
        elif client_rating:
            return client_rating / 5
        return 0.0

    @staticmethod
    def compute_target_job_similarity(job_category, worker_target_jobs):
        """Compute target job similarity."""
        job_category_name = MatchEngine.normalize_string(job_category.name)
        target_job_names = [
            MatchEngine.normalize_string(tj.name) for tj in worker_target_jobs
        ]
        for target_job in target_job_names:
            if SequenceMatcher(None, job_category_name, target_job).ratio() > 0.8:
                return 1.0
        return 0.0

    @staticmethod
    def compute_education_score(job, worker_educations):
        """Match education level/field to job requirements."""
        job_keywords = MatchEngine.normalize_string(job.description + ' ' + job.skills)
        required_field = 'engineering' if 'engineer' in job_keywords else None
        required_level = 'bachelor' if 'degree' in job_keywords else 'any'

        for education in worker_educations:
            field = MatchEngine.normalize_string(education.field or '')
            level = MatchEngine.normalize_string(education.level or '')
            field_match = (
                1.0 if (required_field and required_field in field) else 0.5
            )
            level_match = (
                1.0 if (required_level == 'any' or required_level in level) else 0.5
            )
            return (field_match + level_match) / 2
        return 0.0

    @staticmethod
    def compute_location_similarity(job_location, worker_location):
        """Compute location similarity (low weight)."""
        job_loc = MatchEngine.normalize_string(job_location)
        worker_loc = MatchEngine.normalize_string(worker_location or '')
        return 1.0 if job_loc == worker_loc else 0.5

    @staticmethod
    def store_embedding(entity_type, entity_id, data):
        """Placeholder to store text data for future NLP."""
        # For now, store raw text as JSON (later use BERT/TF-IDF)
        vector = json.dumps({'raw_text': data})
        Embedding.objects.update_or_create(
            entity_type=entity_type,
            entity_id=entity_id,
            defaults={'vector': vector}
        )

    @classmethod
    def match_job_to_workers(cls, job):
        """Match a job to workers."""
        results = []
        workers = Worker.objects.all()
        
        # Store job data for NLP
        job_text = f"{job.title} {job.skills} {job.description} {job.category.name}"
        cls.store_embedding('job', job.id, job_text)

        for worker in workers:
            try:
                # Store worker data for NLP
                worker_text = (
                    f"{[s.name for s in worker.skills.all()]} "
                    f"{[e.field for e in worker.educations.all()]} "
                    f"{[t.name for t in worker.target_jobs.all()]}"
                )
                cls.store_embedding('worker', worker.id, worker_text)

                skill_score = cls.calculate_skill_match(job.skills, worker.skills)
                target_job_score = cls.compute_target_job_similarity(
                    job.category, worker.target_jobs.all()
                )
                experience_score = cls.calculate_experience_score(worker)
                education_score = cls.compute_education_score(
                    job, worker.educations.all()
                )
                location_score = cls.compute_location_similarity(
                    job.location, worker.location
                )
                rating_score = cls.calculate_rating_score(worker)
                total_score = (
                    cls.SKILL_WEIGHT * skill_score +
                    cls.TARGET_JOB_WEIGHT * target_job_score +
                    cls.EXPERIENCE_WEIGHT * experience_score +
                    cls.EDUCATION_WEIGHT * education_score +
                    cls.LOCATION_WEIGHT * location_score +
                    rating_score * 0.1
                )
                # Tie-breaker: Boost if has_experience and recent activity
                if worker.has_experience:
                    total_score += 0.01
                if worker.last_activity:
                    recent = (worker.last_activity > timezone.now() - timedelta(days=30))
                    total_score += 0.01 if recent else 0

                criteria = {
                    'skills': skill_score,
                    'target_job': target_job_score,
                    'experience': experience_score,
                    'education': education_score,
                    'location': location_score,
                    'rating': rating_score
                }
                results.append({
                    'worker': worker,
                    'score': min(max(total_score, 0.0), 1.0),
                    'criteria': criteria
                })
            except Exception as e:
                logger.error(f"Error matching job {job.id} to worker {worker.id}: {str(e)}")
        return sorted(results, key=lambda x: x['score'], reverse=True)[:5]

    @classmethod
    def match_worker_to_jobs(cls, worker):
        """Match a worker to open jobs."""
        results = []
        jobs = Job.objects.filter(status='open')
        
        # Store worker data for NLP
        worker_text = (
            f"{[s.name for s in worker.skills.all()]} "
            f"{[e.field for e in worker.educations.all()]} "
            f"{[t.name for t in worker.target_jobs.all()]}"
        )
        cls.store_embedding('worker', worker.id, worker_text)

        for job in jobs:
            try:
                # Store job data for NLP
                job_text = f"{job.title} {job.skills} {job.description} {job.category.name}"
                cls.store_embedding('job', job.id, job_text)

                skill_score = cls.calculate_skill_match(job.skills, worker.skills)
                target_job_score = cls.compute_target_job_similarity(
                    job.category, worker.target_jobs.all()
                )
                experience_score = cls.calculate_experience_score(worker)
                education_score = cls.compute_education_score(
                    job, worker.educations.all()
                )
                location_score = cls.compute_location_similarity(
                    job.location, worker.location
                )
                rating_score = cls.calculate_rating_score(worker)
                total_score = (
                    cls.SKILL_WEIGHT * skill_score +
                    cls.TARGET_JOB_WEIGHT * target_job_score +
                    cls.EXPERIENCE_WEIGHT * experience_score +
                    cls.EDUCATION_WEIGHT * education_score +
                    cls.LOCATION_WEIGHT * location_score +
                    rating_score * 0.1
                )
                # Tie-breaker
                if worker.has_experience:
                    total_score += 0.01
                if worker.last_activity:
                    recent = (worker.last_activity > timezone.now() - timedelta(days=30))
                    total_score += 0.01 if recent else 0

                criteria = {
                    'skills': skill_score,
                    'target_job': target_job_score,
                    'experience': experience_score,
                    'education': education_score,
                    'location': location_score,
                    'rating': rating_score
                }
                results.append({
                    'job': job,
                    'score': min(max(total_score, 0.0), 1.0),
                    'criteria': criteria
                })
            except Exception as e:
                logger.error(f"Error matching worker {worker.id} to job {job.id}: {str(e)}")
        return sorted(results, key=lambda x: x['score'], reverse=True)[:5]