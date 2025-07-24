from apps.users.models import Worker
from apps.jobs.models import Job, Feedback, ClientFeedback, Category
from .models import Embedding, SkillSynonym, Location, WeightConfig
import logging
from difflib import SequenceMatcher
import re
import json
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Q

logger = logging.getLogger(__name__)

class MatchEngine:
    DEFAULT_SKILL_WEIGHT = 0.45
    DEFAULT_TARGET_JOB_WEIGHT = 0.2
    DEFAULT_EXPERIENCE_WEIGHT = 0.2
    DEFAULT_EDUCATION_WEIGHT = 0.05
    DEFAULT_LOCATION_WEIGHT = 0.1
    DEFAULT_RATING_WEIGHT = 0.1

    @staticmethod
    def normalize_string(s):
        """Normalize strings for comparison."""
        return re.sub(r'\s+', ' ', (s or '').lower().strip())

    @staticmethod
    def extract_keywords(text):
        """Extract keywords from text for rule-based matching."""
        words = re.findall(r'\b\w+\b', MatchEngine.normalize_string(text))
        return [w for w in words if len(w) > 3]  # Filter short words

    @staticmethod
    def calculate_skill_match(job_skills, worker_skills, job_description=''):
        """Match skills, including synonyms and description keywords."""
        job_skill_list = [s.strip().lower() for s in job_skills.split(',') if s.strip()]
        job_keywords = MatchEngine.extract_keywords(job_description)
        worker_skill_set = set(s.name.lower() for s in worker_skills.all())
        
        # Include synonyms
        synonym_map = {s.skill.lower(): [syn.lower() for syn in s.synonyms] for s in SkillSynonym.objects.all()}
        extended_job_skills = set(job_skill_list)
        for skill in job_skill_list:
            extended_job_skills.update(synonym_map.get(skill, []))
        extended_job_skills.update(job_keywords[:5])  # Top 5 keywords from description
        
        if not extended_job_skills:
            return 0.0
        common_skills = extended_job_skills.intersection(worker_skill_set)
        return len(common_skills) / len(extended_job_skills)

    @staticmethod
    def calculate_experience_score(worker):
        """Calculate experience score, capped at 5 years."""
        if not worker.has_experience:
            return 0.0
        return min(worker.years_of_experience / 5, 1.0)

    @staticmethod
    def calculate_rating_score(worker):
        """Calculate normalized rating score."""
        worker_rating = Feedback.objects.filter(worker=worker).aggregate(Avg('rating'))['rating__avg'] or 0
        client_rating = ClientFeedback.objects.filter(worker=worker).aggregate(Avg('rating'))['rating__avg'] or 0
        ratings = [r for r in [worker_rating, client_rating] if r > 0]
        return sum(r / 5 for r in ratings) / len(ratings) if ratings else 0.0

    @staticmethod
    def compute_target_job_similarity(job_category, worker_target_jobs):
        """Compute target job similarity using string matching."""
        job_category_name = MatchEngine.normalize_string(job_category.name)
        target_job_names = [
            MatchEngine.normalize_string(tj.job_title) for tj in worker_target_jobs
        ]
        for target_job in target_job_names:
            if SequenceMatcher(None, job_category_name, target_job).ratio() > 0.8:
                return 1.0
        return 0.0

    @staticmethod
    def compute_education_score(job, worker_educations):
        """Match education, prioritizing certificates for blue-collar jobs."""
        job_keywords = MatchEngine.normalize_string(job.description + ' ' + job.skills)
        is_blue_collar = job.category.name.lower() in ['plumbing', 'electrical', 'construction', 'carpentry']
        
        if is_blue_collar:
            required_level = ['certificate', 'training', 'any']
            required_field = job.category.name.lower()
        else:
            required_field = 'engineering' if 'engineer' in job_keywords else None
            required_level = ['bachelor', 'any'] if 'degree' in job_keywords else ['any']

        for education in worker_educations:
            field = MatchEngine.normalize_string(education.field_of_study or '')
            level = MatchEngine.normalize_string(education.level_of_study or '')
            field_match = 1.0 if (required_field and required_field in field) else 0.5
            level_match = 1.0 if any(l in level for l in required_level) else 0.5
            return (field_match + level_match) / 2
        return 0.0

    @staticmethod
    def compute_location_similarity(job_location, worker_location):
        """Compute location similarity using hierarchy."""
        job_loc = MatchEngine.normalize_string(job_location)
        worker_loc = MatchEngine.normalize_string(worker_location or '')
        if not job_loc or not worker_loc:
            return 0.5
        
        try:
            job_location_obj = Location.objects.get(name__iexact=job_loc)
            worker_location_obj = Location.objects.get(name__iexact=worker_loc)
            
            if job_location_obj == worker_location_obj:
                return 1.0
            # Check parent hierarchy
            current = worker_location_obj
            while current.parent:
                if current.parent == job_location_obj:
                    return 0.9  # Sub-location match
                current = current.parent
            return 0.5  # No hierarchy match
        except Location.DoesNotExist:
            return 0.5 if SequenceMatcher(None, job_loc, worker_loc).ratio() > 0.8 else 0.5

    @staticmethod
    def store_embedding(entity_type, entity_id, data):
        """Store text data and extracted keywords."""
        keywords = MatchEngine.extract_keywords(data)
        vector = json.dumps({'raw_text': data, 'keywords': keywords})
        Embedding.objects.update_or_create(
            entity_type=entity_type,
            entity_id=entity_id,
            defaults={'vector': vector}
        )

    @classmethod
    def get_weights(cls, category):
        """Retrieve category-specific weights."""
        try:
            config = WeightConfig.objects.get(category=category)
            return {
                'skill': config.skill_weight,
                'target_job': config.target_job_weight,
                'experience': config.experience_weight,
                'education': config.education_weight,
                'location': config.location_weight,
                'rating': config.rating_weight
            }
        except WeightConfig.DoesNotExist:
            try:
                config = WeightConfig.objects.get(category__isnull=True)
                return {
                    'skill': config.skill_weight,
                    'target_job': config.target_job_weight,
                    'experience': config.experience_weight,
                    'education': config.education_weight,
                    'location': config.location_weight,
                    'rating': config.rating_weight
                }
            except WeightConfig.DoesNotExist:
                return {
                    'skill': cls.DEFAULT_SKILL_WEIGHT,
                    'target_job': cls.DEFAULT_TARGET_JOB_WEIGHT,
                    'experience': cls.DEFAULT_EXPERIENCE_WEIGHT,
                    'education': cls.DEFAULT_EDUCATION_WEIGHT,
                    'location': cls.DEFAULT_LOCATION_WEIGHT,
                    'rating': cls.DEFAULT_RATING_WEIGHT
                }

    @classmethod
    def match_job_to_workers(cls, job):
        """Match a job to workers with pre-filtering."""
        results = []
        weights = cls.get_weights(job.category)
        
        # Pre-filter workers by location and skills
        job_loc = MatchEngine.normalize_string(job.location)
        job_skills = {s.strip().lower() for s in job.skills.split(',') if s.strip()}
        synonym_map = {s.skill.lower(): [syn.lower() for syn in s.synonyms] for s in SkillSynonym.objects.all()}
        extended_skills = job_skills.copy()
        for skill in job_skills:
            extended_skills.update(synonym_map.get(skill, []))
        
        workers = Worker.objects.filter(
            Q(location__iexact=job_loc) |
            Q(skills__name__in=extended_skills)
        ).distinct().select_related('user')
        # Filter out orphaned workers (no related user)
        workers = [w for w in workers if hasattr(w, 'user') and w.user is not None]
        
        # Store job embedding
        job_text = f"{job.title} {job.skills} {job.description} {job.category.name}"
        cls.store_embedding('job', job.id, job_text)

        for worker in workers:
            try:
                # Store worker embedding
                worker_text = (
                    f"{[s.name for s in worker.skills.all()]} "
                    f"{[e.field_of_study for e in worker.educations.all()]} "
                    f"{[t.job_title for t in worker.target_jobs.all()]}"
                )
                cls.store_embedding('worker', worker.id, worker_text)

                skill_score = cls.calculate_skill_match(job.skills, worker.skills, job.description)
                target_job_score = cls.compute_target_job_similarity(job.category, worker.target_jobs.all())
                experience_score = cls.calculate_experience_score(worker)
                education_score = cls.compute_education_score(job, worker.educations.all())
                location_score = cls.compute_location_similarity(job.location, worker.location)
                rating_score = cls.calculate_rating_score(worker)
                
                total_score = (
                    weights['skill'] * skill_score +
                    weights['target_job'] * target_job_score +
                    weights['experience'] * experience_score +
                    weights['education'] * education_score +
                    weights['location'] * location_score +
                    weights['rating'] * rating_score
                )
                
                # Tie-breakers
                if worker.has_experience:
                    total_score += 0.01
                if worker.last_activity and worker.last_activity > timezone.now() - timedelta(days=30):
                    total_score += 0.01

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
        return sorted(results, key=lambda x: x['score'], reverse=True)[:10]

    @classmethod
    def match_worker_to_jobs(cls, worker):
        """Match a worker to open jobs with pre-filtering."""
        results = []
        weights = cls.get_weights(None)  # Default weights for worker-to-job
        
        # Pre-filter jobs by location and skills
        worker_loc = MatchEngine.normalize_string(worker.location)
        worker_skills = {s.name.lower() for s in worker.skills.all()}
        synonym_map = {s.skill.lower(): [syn.lower() for syn in s.synonyms] for s in SkillSynonym.objects.all()}
        extended_skills = worker_skills.copy()
        for skill in worker_skills:
            extended_skills.update(synonym_map.get(skill, []))
        
        jobs = Job.objects.filter(
            Q(status='open') &
            (Q(location__iexact=worker_loc) | Q(skills__in=extended_skills))
        ).distinct()
        
        # Store worker embedding
        worker_text = (
            f"{[s.name for s in worker.skills.all()]} "
            f"{[e.field_of_study for e in worker.educations.all()]} "
            f"{[t.job_title for t in worker.target_jobs.all()]}"
        )
        cls.store_embedding('worker', worker.id, worker_text)

        for job in jobs:
            try:
                # Store job embedding
                job_text = f"{job.title} {job.skills} {job.description} {job.category.name}"
                cls.store_embedding('job', job.id, job_text)

                skill_score = cls.calculate_skill_match(job.skills, worker.skills, job.description)
                target_job_score = cls.compute_target_job_similarity(job.category, worker.target_jobs.all())
                experience_score = cls.calculate_experience_score(worker)
                education_score = cls.compute_education_score(job, worker.educations.all())
                location_score = cls.compute_location_similarity(job.location, worker.location)
                rating_score = cls.calculate_rating_score(worker)
                
                total_score = (
                    weights['skill'] * skill_score +
                    weights['target_job'] * target_job_score +
                    weights['experience'] * experience_score +
                    weights['education'] * education_score +
                    weights['location'] * location_score +
                    weights['rating'] * rating_score
                )
                
                # Tie-breakers
                if worker.has_experience:
                    total_score += 0.01
                if worker.last_activity and worker.last_activity > timezone.now() - timedelta(days=30):
                    total_score += 0.01

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
        return sorted(results, key=lambda x: x['score'], reverse=True)[:10]