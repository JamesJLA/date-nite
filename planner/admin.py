from django.contrib import admin

from .models import Participant, Plan, Vote


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("id", "inviter_email", "invitee_email", "created_at")
    search_fields = ("inviter_email", "invitee_email")


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "plan", "email", "role")
    search_fields = ("email",)
    list_filter = ("role",)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "participant",
        "dinner_choice",
        "activity_choice",
        "budget_choice",
        "submitted_at",
    )
    list_filter = ("dinner_choice", "activity_choice", "budget_choice")
