from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import CreatePlanForm, VoteForm
from .models import Participant, Plan, Vote
from .services import generate_date_plan


def _get_vote(participant):
    try:
        return participant.vote
    except Vote.DoesNotExist:
        return None


class HomeView(View):
    template_name = "planner/home.html"

    def get(self, request):
        return render(request, self.template_name, {"form": CreatePlanForm()})

    def post(self, request):
        form = CreatePlanForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        with transaction.atomic():
            plan = Plan.objects.create(
                inviter_email=form.cleaned_data["inviter_email"],
                invitee_email=form.cleaned_data["invitee_email"],
            )
            inviter = Participant.objects.create(
                plan=plan,
                email=plan.inviter_email,
                role=Participant.INVITER,
            )
            invitee = Participant.objects.create(
                plan=plan,
                email=plan.invitee_email,
                role=Participant.INVITEE,
            )

        invite_link = request.build_absolute_uri(
            reverse("planner:vote", kwargs={"token": invitee.token})
        )
        send_mail(
            subject="You have a Date Nite invite",
            message=(
                f"Your partner invited you to plan a Valentines date night.\n\n"
                f"Open this link to vote: {invite_link}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitee.email],
            fail_silently=True,
        )

        messages.success(
            request, "Invite created. A voting link was sent to your partner email."
        )
        return redirect("planner:vote", token=inviter.token)


class VoteView(View):
    template_name = "planner/vote.html"

    def get(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan"), token=token
        )
        vote = _get_vote(participant)
        form = VoteForm(instance=vote)
        return render(
            request, self.template_name, {"form": form, "participant": participant}
        )

    def post(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan"), token=token
        )
        vote = _get_vote(participant)
        form = VoteForm(request.POST, instance=vote)
        if not form.is_valid():
            return render(
                request, self.template_name, {"form": form, "participant": participant}
            )

        saved_vote = form.save(commit=False)
        saved_vote.participant = participant
        saved_vote.save()
        if participant.plan.ai_summary:
            participant.plan.ai_summary = ""
            participant.plan.save(update_fields=["ai_summary"])
        messages.success(request, "Your choices are saved.")
        return redirect("planner:results", token=participant.token)


class ResultsView(View):
    template_name = "planner/results.html"

    def get(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan"), token=token
        )
        plan = participant.plan
        participants = plan.participants.all()

        participant_votes = []
        for person in participants:
            participant_votes.append((person, _get_vote(person)))

        all_voted = all(vote is not None for _, vote in participant_votes)
        if all_voted and (
            not plan.ai_summary
            or plan.ai_summary.startswith("Gemini is not configured yet.")
        ):
            plan.ai_summary = generate_date_plan(plan)
            plan.save(update_fields=["ai_summary"])

        invitee = plan.participants.filter(role=Participant.INVITEE).first()
        invitee_link = ""
        if invitee:
            invitee_link = request.build_absolute_uri(
                reverse("planner:vote", kwargs={"token": invitee.token})
            )

        context = {
            "participant": participant,
            "plan": plan,
            "participant_votes": participant_votes,
            "all_voted": all_voted,
            "invitee_link": invitee_link,
        }
        return render(request, self.template_name, context)
