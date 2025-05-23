from rest_framework import serializers
from .models import Job, JobImage, Category, JobApplication, JobRequest, Feedback, PaymentRequest, Payment
from apps.users.models import Worker
from .models import PaymentRequest
from apps.users.serializers import UserSerializer
from core.constants import JOB_STATUS_CHOICES, PAYMENT_METHOD_CHOICES
from .feedback_serializers import FeedbackSerializer
import uuid
import logging

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
        job = self.context.get('job') 
        worker = data['worker']
        logger.debug(f"Validating application: job={job.id}, worker={worker.id}")
        if job.status != 'open':
            logger.error(f"Job {job.id} is not open")
            raise serializers.ValidationError("Cannot apply to a non-open job.")
        if JobApplication.objects.filter(job=job, worker=worker).exists():
            logger.error(f"Worker {worker.id} already applied to job {job.id}")
            raise serializers.ValidationError("You have already applied to this job.")
        if JobRequest.objects.filter(
            application__worker=worker,
            status='pending'
        ).exists():
            logger.error(f"Worker {worker.id} has pending requests")
            raise serializers.ValidationError("You have pending job requests. Please respond to them first.")
        return data

    def create(self, validated_data):
        job = self.context.get('job')  
        validated_data['job'] = job  
        return super().create(validated_data)


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
        job_id = self.context.get('job_id')
        if job_id and job.id != job_id:
            raise serializers.ValidationError("The application does not belong to the specified job.")
        if job.status != 'open':
            raise serializers.ValidationError("Cannot send request for a non-open job.")
        if JobRequest.objects.filter(application=application).exists():
            raise serializers.ValidationError("A request has already been sent for this application.")
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
    # Read-only fields
    category = CategorySerializer(read_only=True)
    images = JobImageSerializer(many=True, read_only=True)
    applications = JobApplicationSerializer(many=True, read_only=True)
    assigned_worker = WorkerProfileSerializer(read_only=True)
    status = serializers.ChoiceField(choices=JOB_STATUS_CHOICES, read_only=True)
    
    # Write-only fields
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
    
    # Regular fields
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES)

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
        extra_kwargs = {
            'category_id': {'write_only': True},
            'uploaded_images': {'write_only': True}
        }

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

class PaymentConfirmSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    tx_ref = serializers.CharField(max_length=100, required=False, read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'job', 'client', 'worker', 'payment_method', 'amount', 'tx_ref', 'transaction_id', 'status', 'created_at']
        read_only_fields = ['client', 'worker', 'payment_method', 'tx_ref', 'transaction_id', 'status', 'created_at']

    def validate(self, data):
        job = self.context['job']  # Use job from context instead of querying
        client = self.context['request'].user
        if job.status != 'pending_payment':
            raise serializers.ValidationError("Cannot confirm payment for a job not pending payment.")
        if job.client != client:
            raise serializers.ValidationError("Only the job's client can confirm payment.")
        if Payment.objects.filter(job=job).exists():
            raise serializers.ValidationError("Payment already confirmed for this job.")
        if data.get('payment_method', job.payment_method) != job.payment_method:
            raise serializers.ValidationError("Payment method must match the job's payment method.")
        if job.payment_method != 'cash' and not data.get('amount'):
            raise serializers.ValidationError("Amount is required for non-cash payments.")
        return data

    def create(self, validated_data):
        job = self.context['job']
        validated_data['client'] = self.context['request'].user
        validated_data['worker'] = job.assigned_worker
        validated_data['payment_method'] = job.payment_method
        validated_data['tx_ref'] = f"job-{job.id}-{uuid.uuid4().hex[:10]}"
        validated_data['status'] = 'pending' if job.payment_method == 'chapa' else 'completed'
        return Payment.objects.create(**validated_data)