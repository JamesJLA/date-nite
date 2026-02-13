from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import CreatePlanForm, RefinePlanForm, VoteForm
from .models import Participant, Plan, Vote
from .services import generate_date_plan


def _get_vote(participant):
    try:
        return participant.vote
    except Vote.DoesNotExist:
        return None


def _format_story(summary: str):
    if not summary:
        return "", [], ""

    lines = [line.strip() for line in summary.splitlines() if line.strip()]
    if not lines:
        return "", [], ""

    intro_parts = []
    steps = []
    closing_parts = []
    in_steps = False
    for line in lines:
        if line.startswith(("-", "*", "•")):
            in_steps = True
            steps.append(line.lstrip("-*• ").strip())
            continue
        if in_steps:
            closing_parts.append(line)
        else:
            intro_parts.append(line)

    if not steps and len(intro_parts) > 1:
        steps = intro_parts[1:]
        intro_parts = intro_parts[:1]

    intro = " ".join(intro_parts)
    closing = " ".join(closing_parts)
    return intro, steps, closing


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
                city=form.cleaned_data["city"],
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

    def _build_context(self, request, participant):
        plan = participant.plan
        participants = plan.participants.all()

        participant_votes = []
        for person in participants:
            participant_votes.append((person, _get_vote(person)))

        all_voted = all(vote is not None for _, vote in participant_votes)
        invitee = plan.participants.filter(role=Participant.INVITEE).first()
        invitee_link = ""
        if invitee:
            invitee_link = request.build_absolute_uri(
                reverse("planner:vote", kwargs={"token": invitee.token})
            )

        return {
            "participant": participant,
            "plan": plan,
            "participant_votes": participant_votes,
            "all_voted": all_voted,
            "invitee_link": invitee_link,
            "can_generate": all_voted and settings.ENABLE_AI,
            "ai_enabled": settings.ENABLE_AI,
            "story": _format_story(plan.ai_summary),
            "refine_form": RefinePlanForm(),
        }

    def get(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan"), token=token
        )
        context = self._build_context(request, participant)
        return render(request, self.template_name, context)

    def post(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan"), token=token
        )
        context = self._build_context(request, participant)

        if not context["all_voted"]:
            messages.warning(request, "Both of you must vote before generating a plan.")
            return redirect("planner:results", token=participant.token)

        if not settings.ENABLE_AI:
            messages.warning(request, "AI generation is disabled for this environment.")
            return redirect("planner:results", token=participant.token)

        action = request.POST.get("action", "generate")
        locale_hint = request.headers.get("Accept-Language", "en-US")
        plan = participant.plan

        if action == "refine":
            refine_form = RefinePlanForm(request.POST)
            if not refine_form.is_valid():
                context["refine_form"] = refine_form
                return render(request, self.template_name, context)
            if not plan.ai_summary:
                messages.warning(request, "Generate a first plan before refining it.")
                return redirect("planner:results", token=participant.token)

            plan.ai_summary = generate_date_plan(
                plan,
                locale_hint=locale_hint,
                feedback=refine_form.cleaned_data["feedback"],
                previous_summary=plan.ai_summary,
            )
            plan.save(update_fields=["ai_summary"])
            messages.success(request, "Plan refined based on your feedback.")
            return redirect("planner:results", token=participant.token)

        plan.ai_summary = generate_date_plan(plan, locale_hint=locale_hint)
        plan.save(update_fields=["ai_summary"])
        messages.success(request, "AI plan generated.")
        return redirect("planner:results", token=participant.token)
