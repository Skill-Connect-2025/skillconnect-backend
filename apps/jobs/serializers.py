from rest_framework import serializers
from .models import Job, JobImage, Category, JobApplication, JobRequest, Feedback, PaymentRequest, Transaction, ClientFeedback, Dispute
from apps.users.models import Worker
from .models import PaymentRequest
from apps.users.serializers import UserSerializer
from core.constants import JOB_STATUS_CHOICES, PAYMENT_METHOD_CHOICES, JOB_REQUEST_STATUS_CHOICES
from .feedback_serializers import FeedbackSerializer
import uuid
import logging
from django.views.decorators.csrf import csrf_exempt
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Avg, Count
from apps.users.models import User

logger = logging.getLogger('django')

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class JobImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobImage
        fields = ['id', 'image']

class WorkerProfileSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = Worker
        fields = [
            'id', 'user', 'profile_pic', 'location', 'birthdate', 'nationality',
            'gender', 'has_experience', 'years_of_experience', 'educations',
            'skills', 'target_jobs'
        ]
        ref_name = 'JobsWorkerProfile'

    def get_user(self, obj):
        # Defensive: Return None if related user does not exist
        try:
            user = obj.user
        except Exception:
            return None
        return {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone_number': user.phone_number or 'Not provided'
        }

class PublicWorkerProfileSerializer(serializers.ModelSerializer):
    rating_stats = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = Worker
        fields = ['id', 'user', 'skills', 'location', 'profile_pic', 'rating_stats']

    def get_user(self, obj):
        # Defensive: Return None if related user does not exist
        try:
            user = obj.user
        except Exception:
            return None
        return {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name
        }

    def get_rating_stats(self, obj):
        # Calculate rating stats from Feedback and ClientFeedback
        try:
            worker_ratings = Feedback.objects.filter(job__assigned_worker=obj).aggregate(
                average_rating=Avg('rating'), rating_count=Count('rating')
            )
            stats = {
                'average_rating': worker_ratings['average_rating'] or 0.0,
                'rating_count': worker_ratings['rating_count'] or 0
            }
            return stats
        except Exception as e:
            logger.error(f"Error calculating rating_stats for worker {obj.id}: {str(e)}")
            return {'average_rating': 0.0, 'rating_count': 0}

class JobApplicationSerializer(serializers.ModelSerializer):
    worker = PublicWorkerProfileSerializer(read_only=True)
    worker_id = serializers.PrimaryKeyRelatedField(
        queryset=Worker.objects.all(), write_only=True, source='worker'
    )

    class Meta:
        model = JobApplication
        fields = ['id', 'job', 'worker', 'worker_id', 'status', 'applied_at']
        read_only_fields = ['status', 'applied_at']

    def validate(self, data):
        job = self.context.get('job')
        worker = data['worker']
        if job.status != 'open':
            raise serializers.ValidationError("Cannot apply to a non-open job.")
        if JobApplication.objects.filter(job=job, worker=worker).exists():
            raise serializers.ValidationError("You have already applied to this job.")
        # Removed validation for pending job requests
        return data

    def create(self, validated_data):
        job = self.context.get('job')
        validated_data['job'] = job
        return super().create(validated_data)


class ClientFeedbackSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = ClientFeedback
        fields = ['id', 'job', 'worker', 'client', 'rating', 'review', 'created_at']
        read_only_fields = ['job', 'worker', 'client', 'created_at']

    def validate(self, data):
        job = self.context['job']
        worker = self.context['worker']
        if job.status != 'completed':
            raise serializers.ValidationError("Cannot submit feedback for a non-completed job.")
        if job.assigned_worker != worker:
            raise serializers.ValidationError("Only the assigned worker can submit feedback.")
        if ClientFeedback.objects.filter(job=job).exists():
            raise serializers.ValidationError("Feedback already submitted for this job.")
        return data

    def create(self, validated_data):
        job = self.context['job']
        worker = self.context['worker']
        return ClientFeedback.objects.create(
            job=job,
            worker=worker,
            client=job.client,
            rating=validated_data['rating'],
            review=validated_data.get('review', '')
        )

class JobRequestSerializer(serializers.ModelSerializer):
    worker = WorkerProfileSerializer(read_only=True)
    worker_id = serializers.PrimaryKeyRelatedField(
        queryset=Worker.objects.all(), write_only=True, source='worker'
    )

    class Meta:
        model = JobRequest
        fields = ['id', 'job', 'worker', 'worker_id', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

    def validate(self, data):
        job = self.context.get('job')
        worker = data['worker']
        
        if job.status != 'open':
            raise serializers.ValidationError("Cannot send request for a non-open job.")
        
        if JobRequest.objects.filter(job=job, worker=worker).exists():
            raise serializers.ValidationError("A request has already been sent to this worker.")
        
        if job.assigned_worker:
            raise serializers.ValidationError("This job already has an assigned worker.")
        
        return data

class JobRequestResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['accepted', 'rejected'])

    def validate(self, data):
        job_request = self.context['job_request']
        
        if job_request.status != 'pending':
            raise serializers.ValidationError("This request has already been processed.")
        
        if data['status'] == 'accepted':
            job = job_request.job
            if job.status != 'open':
                raise serializers.ValidationError("This job is no longer available.")
            if job.assigned_worker:
                raise serializers.ValidationError("This job already has an assigned worker.")
        
        return data

class JobStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['completed'])

    def validate(self, data):
        job = self.context['job']
        user = self.context['request'].user
        
        # Check if job is in progress
        if job.status not in ['in_progress', 'client_completed', 'worker_completed']:
            raise serializers.ValidationError("Job must be in progress or partially completed.")
        
        # Check if job has an assigned worker
        if not job.assigned_worker:
            raise serializers.ValidationError("Cannot complete a job without an assigned worker.")
        
        # Check if user is either client or worker
        if user != job.client and (not hasattr(user, 'worker') or user.worker != job.assigned_worker):
            raise serializers.ValidationError("Only the client or assigned worker can mark the job as completed.")
        
        return data

class PaymentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRequest
        fields = ['id', 'job', 'worker', 'message', 'created_at']
        read_only_fields = ['job', 'worker', 'message', 'created_at']

    def validate(self, data):
        job = self.context['job']
        worker = self.context['worker']
        
        # Check if job is completed
        if job.status != 'completed':
            raise serializers.ValidationError("Cannot request payment for a non-completed job.")
        
        # Check if worker is assigned to the job
        if not JobApplication.objects.filter(job=job, worker=worker, status='accepted').exists():
            raise serializers.ValidationError("Only the assigned worker can request payment.")
        
        # Check if payment request already exists
        if PaymentRequest.objects.filter(job=job).exists():
            raise serializers.ValidationError("Payment request already exists.")
        
        return data

    def create(self, validated_data):
        return PaymentRequest.objects.create(
            job=self.context['job'],
            worker=self.context['worker'],
            message="Payment requested for completed job."
        )


class JobSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    images = JobImageSerializer(many=True, read_only=True)
    applications = JobApplicationSerializer(many=True, read_only=True)
    assigned_worker = WorkerProfileSerializer(read_only=True)
    status = serializers.ChoiceField(choices=JOB_STATUS_CHOICES, read_only=True)
    
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=True),
        write_only=True,
        required=False,
        allow_null=True,
        default=[]
    )
    
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    client = serializers.ReadOnlyField(source='client.username')

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'location', 'skills', 'description', 'client',
            'created_at', 'updated_at', 'category', 'category_id', 'images',
            'uploaded_images', 'payment_method', 'status', 'applications',
            'assigned_worker'
        ]
        read_only_fields = [
            'id', 'client', 'status', 'created_at', 'updated_at',
            'images', 'applications', 'assigned_worker'
        ]

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        validated_data.pop('client', None)
        job = Job.objects.create(client=self.context['request'].user, **validated_data)
        for image in uploaded_images:
            if image:
                JobImage.objects.create(job=job, image=image)
        return job

    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if uploaded_images is not None and uploaded_images != []:
            instance.images.all().delete()
            for image in uploaded_images:
                if image:
                    JobImage.objects.create(job=instance, image=image)
        return instance


class TransactionSerializer(serializers.ModelSerializer):
    amount = serializers.FloatField(min_value=0.01)

    class Meta:
        model = Transaction
        fields = [
            'id', 'job', 'client', 'worker', 'amount', 'currency', 'tx_ref',
            'transaction_id', 'payment_method', 'status', 'created_at'
        ]
        read_only_fields = [
            'id', 'job', 'client', 'worker', 'currency', 'tx_ref',
            'transaction_id', 'payment_method', 'status', 'created_at'
        ]

    def validate(self, data):
        job = self.context['job']
        amount = data['amount']

        # Check job status
        if job.status != 'pending_payment':
            raise serializers.ValidationError("Job must be in pending_payment status.")

        # Check payment method
        if job.payment_method != 'chapa':
            raise serializers.ValidationError("Job must use Chapa payment method.")

        # Check if transaction already exists
        if Transaction.objects.filter(job=job, status='pending').exists():
            raise serializers.ValidationError("A pending transaction already exists for this job.")

        return data

class DisputeSerializer(serializers.ModelSerializer):
    reported_by = UserSerializer(read_only=True)
    reported_user = UserSerializer(read_only=True)
    resolved_by = UserSerializer(read_only=True)
    job = JobSerializer(read_only=True)

    class Meta:
        model = Dispute
        fields = [
            'id', 'job', 'reported_by', 'reported_user', 'dispute_type',
            'description', 'status', 'resolution', 'resolved_by',
            'created_at', 'updated_at', 'resolved_at'
        ]
        read_only_fields = [
            'id', 'reported_by', 'reported_user', 'status', 'resolution',
            'resolved_by', 'created_at', 'updated_at', 'resolved_at'
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Defensive: If related user is missing, return None instead of raising error
        from django.core.exceptions import ObjectDoesNotExist
        for field in ['reported_by', 'reported_user', 'resolved_by']:
            try:
                # Access the related user to trigger DoesNotExist if missing
                getattr(instance, field)
            except ObjectDoesNotExist:
                rep[field] = None
        return rep

    def validate(self, data):
        job = self.context['job']
        user = self.context['request'].user
        reported_user = self.context['reported_user']

        # Check if user is either client or worker of the job
        if user != job.client and (not hasattr(user, 'worker') or user.worker != job.assigned_worker):
            raise serializers.ValidationError("You can only report disputes for jobs you're involved in.")

        # Check if reported user is the other party in the job
        if reported_user != job.client and (not hasattr(reported_user, 'worker') or reported_user.worker != job.assigned_worker):
            raise serializers.ValidationError("You can only report disputes against the other party in the job.")

        # Check if there's already an active dispute for this job
        if Dispute.objects.filter(job=job, status__in=['pending', 'in_review']).exists():
            raise serializers.ValidationError("There is already an active dispute for this job.")

        return data

    def create(self, validated_data):
        return Dispute.objects.create(
            job=self.context['job'],
            reported_by=self.context['request'].user,
            reported_user=self.context['reported_user'],
            **validated_data
        )