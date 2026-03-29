from django.db import models
from rest_framework import serializers

# Create your models here.

class ProductModel(models.Model):
    title = models.CharField()
    discriptions = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rates = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    created = models.DateTimeField(auto_now_add=True)