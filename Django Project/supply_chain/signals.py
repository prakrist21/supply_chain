from django.db.models.signals import post_save
from django.dispatch import receiver

from supply_chain.models import Project,Team


@receiver(post_save, sender=Project)
def create_project_team(sender, instance, created, **kwargs):
    """Automatically create a team when a project is created"""
    if created:
        Team.objects.create(
            project=instance,
            name=f"{instance.title} Team"
        )