from django.db import models


class Project(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    start_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def refresh_status(self):
        places = self.places.all()
        if places.exists() and not places.filter(visited=False).exists():
            self.status = self.STATUS_COMPLETED
            self.save(update_fields=['status'])


class ProjectPlace(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='places')
    external_id = models.IntegerField()
    title = models.CharField(max_length=500)
    artist = models.CharField(max_length=500, blank=True, default='')
    thumbnail_url = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    visited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('project', 'external_id')

    def __str__(self):
        return f'{self.project.name} – {self.title}'
