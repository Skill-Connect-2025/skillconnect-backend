from apps.users.models import Worker
from apps.jobs.models import Job
from .models import Embedding
import logging
from difflib import SequenceMatcher
import re
import json
from django.utils import timezone
from datetime import timedelta


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
    def compute_skill_similarity(job_skills, worker_skills):
        """Compute skill similarity."""
        job_skills_set = set(
            MatchEngine.normalize_string(skill) for skill in job_skills.split(',')
        )
        worker_skills_set = set(
            MatchEngine.normalize_string(skill.name) for skill in worker_skills
        )
        common_skills = job_skills_set.intersection(worker_skills_set)
        total_skills = job_skills_set.union(worker_skills_set)
        score = len(common_skills) / len(total_skills) if total_skills else 0
        return score

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
    def compute_experience_score(job, worker):
        """Estimate required experience from job skills/description."""
        # Infer required years from skills complexity (simplified)
        skill_count = len(job.skills.split(','))
        required_years = min(5, skill_count * 2)  # e.g., 3 skills -> 6 years, capped at 5
        actual_years = worker.years_of_experience or 0
        score = min(actual_years / required_years, 1.0) if required_years > 0 else 0.5
        return score

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

                skill_score = cls.compute_skill_similarity(
                    job.skills, worker.skills.all()
                )
                target_job_score = cls.compute_target_job_similarity(
                    job.category, worker.target_jobs.all()
                )
                experience_score = cls.compute_experience_score(job, worker)
                education_score = cls.compute_education_score(
                    job, worker.educations.all()
                )
                location_score = cls.compute_location_similarity(
                    job.location, worker.location
                )
                total_score = (
                    cls.SKILL_WEIGHT * skill_score +
                    cls.TARGET_JOB_WEIGHT * target_job_score +
                    cls.EXPERIENCE_WEIGHT * experience_score +
                    cls.EDUCATION_WEIGHT * education_score +
                    cls.LOCATION_WEIGHT * location_score
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
                    'location': location_score
                }
                results.append({
                    'worker': worker,
                    'score': min(max(total_score, 0.0), 1.0),
                    'criteria': criteria
                })
            except Exception as e:
                logger.error(f"Error matching job {job.id} to worker {worker.id}: {str(e)}")
        return sorted(results, key=lambda x: x['score'], reverse=True)

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

                skill_score = cls.compute_skill_similarity(
                    job.skills, worker.skills.all()
                )
                target_job_score = cls.compute_target_job_similarity(
                    job.category, worker.target_jobs.all()
                )
                experience_score = cls.compute_experience_score(job, worker)
                education_score = cls.compute_education_score(
                    job, worker.educations.all()
                )
                location_score = cls.compute_location_similarity(
                    job.location, worker.location
                )
                total_score = (
                    cls.SKILL_WEIGHT * skill_score +
                    cls.TARGET_JOB_WEIGHT * target_job_score +
                    cls.EXPERIENCE_WEIGHT * experience_score +
                    cls.EDUCATION_WEIGHT * education_score +
                    cls.LOCATION_WEIGHT * location_score
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
                    'location': location_score
                }
                results.append({
                    'job': job,
                    'score': min(max(total_score, 0.0), 1.0),
                    'criteria': criteria
                })
            except Exception as e:
                logger.error(f"Error matching worker {worker.id} to job {job.id}: {str(e)}")
        return sorted(results, key=lambda x: x['score'], reverse=True)