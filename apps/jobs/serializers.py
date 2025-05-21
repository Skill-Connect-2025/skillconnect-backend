from rest_framework import serializers
from .models import Job, JobImage, Category, JobApplication, JobRequest, Feedback, PaymentRequest
from apps.users.models import Worker
from .models import PaymentRequest
from apps.users.serializers import UserSerializer
from core.constants import JOB_STATUS_CHOICES, PAYMENT_METHOD_CHOICES

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class JobImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobImage
        fields = ['id', 'image']

class WorkerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Worker
        fields = [
            'id', 'user', 'profile_pic', 'location', 'birthdate', 'nationality',
            'gender', 'has_experience', 'years_of_experience', 'educations',
            'skills', 'target_jobs'
        ]
        ref_name = 'JobsWorkerProfile'


class JobApplicationSerializer(serializers.ModelSerializer):
    worker = WorkerProfileSerializer(read_only=True)
    worker_id = serializers.PrimaryKeyRelatedField(
        queryset=Worker.objects.all(), write_only=True, source='worker'
    )

    class Meta:
        model = JobApplication
        fields = ['id', 'job', 'worker', 'worker_id', 'status', 'applied_at']
        read_only_fields = ['status', 'applied_at']

    def validate(self, data):
        job = data['job']
        worker = data['worker']
        
        # Check if job is open
        if job.status != 'open':
            raise serializers.ValidationError("Cannot apply to a non-open job.")
        
        # Check if worker has already applied
        if JobApplication.objects.filter(job=job, worker=worker).exists():
            raise serializers.ValidationError("You have already applied to this job.")
        
        # Check if worker has any pending requests
        if JobRequest.objects.filter(
            application__worker=worker,
            status='pending'
        ).exists():
            raise serializers.ValidationError("You have pending job requests. Please respond to them first.")
        
        return data

class JobRequestSerializer(serializers.ModelSerializer):
    application = JobApplicationSerializer(read_only=True)
    application_id = serializers.PrimaryKeyRelatedField(
        queryset=JobApplication.objects.all(), write_only=True, source='application'
    )

    class Meta:
        model = JobRequest
        fields = ['id', 'application', 'application_id', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']

    def validate(self, data):
        application = data['application']
        job = application.job
        
        # Check if job is still open
        if job.status != 'open':
            raise serializers.ValidationError("Cannot send request for a non-open job.")
        
        # Check if a request already exists
        if JobRequest.objects.filter(application=application).exists():
            raise serializers.ValidationError("A request has already been sent for this application.")
        
        # Check if job already has an assigned worker
        if job.assigned_worker:
            raise serializers.ValidationError("This job already has an assigned worker.")
        
        return data

class JobRequestResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['accepted', 'rejected'])

    def validate(self, data):
        job_request = self.context['job_request']
        
        # Check if request is still pending
        if job_request.status != 'pending':
            raise serializers.ValidationError("This request has already been processed.")
        
        # If accepting, check if job is still available
        if data['status'] == 'accepted':
            job = job_request.application.job
            if job.status != 'open':
                raise serializers.ValidationError("This job is no longer available.")
            if job.assigned_worker:
                raise serializers.ValidationError("This job already has an assigned worker.")
        
        return data

class JobStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['completed'])

    def validate(self, data):
        job = self.context['job']
        
        # Check if job is in progress
        if job.status != 'in_progress':
            raise serializers.ValidationError("Only jobs in progress can be marked as completed.")
        
        # Check if job has an assigned worker
        if not job.assigned_worker:
            raise serializers.ValidationError("Cannot complete a job without an assigned worker.")
        
        return data

class PaymentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRequest
        fields = ['id', 'job', 'worker', 'message', 'created_at']
        read_only_fields = ['worker', 'created_at']

    def validate(self, data):
        job = data['job']
        worker = self.context['request'].user.worker
        
        # Check if job is completed
        if job.status != 'completed':
            raise serializers.ValidationError("Cannot request payment for a non-completed job.")
        
        # Check if worker is assigned to the job
        if job.assigned_worker != worker:
            raise serializers.ValidationError("Only the assigned worker can request payment.")
        
        # Check if payment request already exists
        if PaymentRequest.objects.filter(job=job).exists():
            raise serializers.ValidationError("Payment request already exists.")
        
        return data


class JobSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    images = JobImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=True), 
        write_only=True, 
        required=False, 
        allow_null=True, 
        default=[]
    )
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    status = serializers.ChoiceField(choices=JOB_STATUS_CHOICES, read_only=True)
    applications = JobApplicationSerializer(many=True, read_only=True)
    assigned_worker = WorkerProfileSerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'location', 'skills', 'description', 'category',
            'category_id', 'payment_method', 'status', 'created_at', 'updated_at',
            'images', 'uploaded_images', 'applications', 'assigned_worker'
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

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'job', 'worker', 'client', 'rating', 'review', 'created_at']
        read_only_fields = ['worker', 'client', 'created_at']

    def validate(self, data):
        job = data['job']
        client = self.context['request'].user
    
        if job.status != 'completed':
            raise serializers.ValidationError("Cannot submit feedback for a non-completed job.")
        
        if job.client != client:
            raise serializers.ValidationError("Only the job's client can submit feedback.")
        if Feedback.objects.filter(job=job).exists():
            raise serializers.ValidationError("Feedback already submitted for this job.")
        return data