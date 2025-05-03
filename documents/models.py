from django.db import models

# Create your models here.
class Client(models.Model):
    """Represents a client (customer)"""
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")

    #Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """String representation of the Client object"""
        return self.name
    
    
