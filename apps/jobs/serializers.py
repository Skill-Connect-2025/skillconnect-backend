from rest_framework import serializers
from .models import Job, JobImage, Category, JobApplication, JobRequest
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
        if job.status != 'open':
            raise serializers.ValidationError("Cannot apply to a non-open job.")
        if JobApplication.objects.filter(job=job, worker=data['worker']).exists():
            raise serializers.ValidationError("You have already applied to this job.")
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
        if job.status != 'open':
            raise serializers.ValidationError("Cannot send request for a non-open job.")
        if JobRequest.objects.filter(application=application).exists():
            raise serializers.ValidationError("A request has already been sent for this application.")
        return data

class PaymentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRequest
        fields = ['id', 'job', 'worker', 'message', 'created_at']
        read_only_fields = ['worker', 'created_at']

    def validate(self, data):
        job = data['job']
        if job.status != 'completed':
            raise serializers.ValidationError("Cannot request payment for a non-completed job.")
        if job.assigned_worker != self.context['request'].user.worker:
            raise serializers.ValidationError("Only the assigned worker can request payment.")
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