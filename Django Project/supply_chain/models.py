import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

class Council(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    contact_email = models.EmailField()
    slug = models.SlugField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} Council'

    class Meta:
        db_table = 'Council'


class Project(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    budget = models.IntegerField()
    council = models.ForeignKey(Council, on_delete=models.CASCADE)
    STATUS_CHOICES = [('active', 'Active'),('completed', 'Completed'),('expired', 'Expired'),]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField(default=datetime.date.today)
    end_date = models.DateField(default='2027-01-01')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def days_until_end(self):
        """Calculate days remaining until end date"""
        from django.utils import timezone
        delta = self.end_date - timezone.now().date()
        return delta.days

    def is_ending_soon(self):
        """Check if project is ending within 7 days"""
        return 0 < self.days_until_end() <= 7

    def is_expired(self):
        """Check if project is closed (completed or expired)"""
        from django.utils import timezone
        if self.status in ['completed', 'expired']:
            return True
        if timezone.now().date() > self.end_date:
            return True
        return False

    def can_be_ended(self):
        """Check if project can be manually ended (no pending bids)"""
        if self.status != 'active':
            return False, "Project is already closed"

        pending_bids = self.bids.filter(status='pending').count()
        if pending_bids > 0:
            return False, f"Cannot end project. You have {pending_bids} pending bid(s). Please approve or reject them first."

        return True, "OK"

    def __str__(self):
        return f'{self.title}'

    class Meta:
        db_table = 'Project'

class Package(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    budget = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    def has_approved_bid(self):
        return self.bids.filter(status='approved').exists()

    def get_approved_bid(self):
        return self.bids.filter(status='approved').first()

    def __str__(self):
        return f'{self.title} - {self.project.title}'

    class Meta:
        db_table = 'Package'
        ordering = ['-created_at']
        verbose_name = 'Package'
        verbose_name_plural = 'Packages'

class Contractor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    contact_email = models.EmailField()
    slug = models.SlugField(max_length=100)
    experience = models.IntegerField()
    role = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f'{self.name} Contractor'

    class Meta:
        db_table = 'Contractor'

class Bid(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        choices=STATUS_CHOICES,
        max_length=20,
        default='pending'
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bids')
    contractor = models.ForeignKey(Contractor, on_delete=models.CASCADE, related_name='bids')
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='bids')
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='bids')

    date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    document1 = models.FileField(upload_to='bid_documents/', null=True, blank=True)
    document2 = models.FileField(upload_to='bid_documents/', null=True, blank=True)
    document3 = models.FileField(upload_to='bid_documents/', null=True, blank=True)

    def clean(self):
        if not self.package_id:
            return

        if self.amount and self.amount > self.package.budget:
            raise ValidationError(f'Bid amount cannot exceed package budget of {self.package.budget}')

        if self.package.has_approved_bid():
            raise ValidationError('This package already has an approved bid. No more bids are allowed.')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Bid #{self.id} - {self.contractor.name} on {self.project.title}'

    class Meta:
        db_table = 'Bid'
        ordering = ['-created_at']
        verbose_name = 'Bid'
        verbose_name_plural = 'Bids'
        unique_together = [['contractor', 'package']]

class Team(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='team',
        primary_key=True
    )
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Team for {self.project.title}'

    def get_members(self):
        """Get all approved bids (contractor-package pairs) for this project"""
        return Bid.objects.filter(
            package__project=self.project,
            status='approved'
        ).select_related('contractor', 'contractor__user', 'package').order_by('package__title')

    def get_contractors(self):
        """Get unique contractors in the team"""
        return Contractor.objects.filter(
            bids__package__project=self.project,
            bids__status='approved'
        ).distinct()

    def member_count(self):
        """Get total number of approved bids (members)"""
        return self.get_members().count()

    def contractor_count(self):
        """Get number of unique contractors"""
        return self.get_contractors().count()

    class Meta:
        db_table = 'Team'
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'

class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('project_created', 'Project Created'),
        ('package_created', 'Package Created'),
        ('package_deleted', 'Package Deleted'),
        ('bid_placed', 'Bid Placed'),
        ('bid_approved', 'Bid Approved'),
        ('bid_received', 'Bid Received'),
        ('bid_rejected', 'Bid Rejected'),
        ('project_ended', 'Project Ended'),
        ('project_deleted', 'Project Deleted'),
        ('profile_updated', 'Profile Updated'),
        ('password_changed', 'Password Changed'),
        ('report_downloaded', 'Report Downloaded'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    message = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True)
    bid = models.ForeignKey(Bid, on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.activity_type} - {self.created_at}'

    class Meta:
        db_table = 'Activity'
        ordering = ['-created_at']
        verbose_name_plural = 'Activities'