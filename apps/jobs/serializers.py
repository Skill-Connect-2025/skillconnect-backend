from rest_framework import serializers
from .models import Job, JobImage, Category
from core.constants import JOB_STATUS_CHOICES, PAYMENT_METHOD_CHOICES

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class JobImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobImage
        fields = ['id', 'image']

class JobSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    images = JobImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    status = serializers.ChoiceField(choices=JOB_STATUS_CHOICES, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'location', 'skills', 'description', 'category',
            'category_id', 'payment_method', 'status', 'created_at', 'updated_at',
            'images', 'uploaded_images'
        ]

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        job = Job.objects.create(**validated_data, status='open')
        for image in uploaded_images:
            JobImage.objects.create(job=job, image=image)
        return job

    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if uploaded_images is not None:
            instance.images.all().delete()
            for image in uploaded_images:
                JobImage.objects.create(job=instance, image=image)
        return instance