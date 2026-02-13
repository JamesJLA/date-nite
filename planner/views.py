from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import CreatePlanForm, RefinePlanForm, SignUpForm, VoteForm
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


def _claim_participant_for_user(request, participant):
    if not request.user.is_authenticated:
        return participant
    if not request.user.email:
        return participant
    if request.user.email.strip().lower() != participant.email.strip().lower():
        return participant

    updated = False
    if participant.user_id is None:
        participant.user = request.user
        participant.save(update_fields=["user"])
        updated = True
    if (
        participant.role == Participant.INVITER
        and participant.plan.created_by_id is None
    ):
        participant.plan.created_by = request.user
        participant.plan.save(update_fields=["created_by"])
        updated = True

    if updated:
        messages.info(
            request,
            "This invite is now linked to your account so your plans stay saved.",
        )
    return participant


def _enforce_participant_access(request, participant):
    if participant.user_id is None:
        return None
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to access your saved date invite.")
        return redirect(f"{reverse('planner:login')}?next={request.get_full_path()}")
    if request.user.pk != participant.user_id:
        messages.error(request, "That invite belongs to a different account.")
        return redirect("planner:home")
    return None


def _build_user_dashboard(user):
    plans = (
        Plan.objects.filter(participants__user=user)
        .distinct()
        .prefetch_related("participants__vote", "participants__user")
        .order_by("-created_at")
    )

    cards = []
    connections = {}

    for plan in plans:
        participants = list(plan.participants.all())
        my_participant = next(
            (person for person in participants if person.user_id == user.id), None
        )
        partner = next(
            (person for person in participants if person.user_id != user.id), None
        )
        if not my_participant or not partner:
            continue

        voted_count = sum(1 for person in participants if _get_vote(person))
        cards.append(
            {
                "plan": plan,
                "my_token": my_participant.token,
                "partner": partner,
                "voted_count": voted_count,
                "all_voted": voted_count == len(participants),
            }
        )

        partner_key = partner.email.strip().lower()
        partner_name = partner.email
        if partner.user_id:
            partner_name = partner.user.email or partner.user.username
        item = connections.get(partner_key)
        if item is None:
            connections[partner_key] = {
                "name": partner_name,
                "count": 1,
                "last_plan": plan,
            }
        else:
            item["count"] += 1
            if plan.created_at > item["last_plan"].created_at:
                item["last_plan"] = plan

    sorted_connections = sorted(
        connections.values(),
        key=lambda entry: entry["last_plan"].created_at,
        reverse=True,
    )
    return cards, sorted_connections


class SignUpView(View):
    template_name = "planner/signup.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("planner:home")
        return render(request, self.template_name, {"form": SignUpForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("planner:home")

        form = SignUpForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = form.save()
        login(request, user)
        messages.success(request, "Welcome! Your account is ready.")
        return redirect("planner:home")


class HomeView(LoginRequiredMixin, View):
    template_name = "planner/home.html"
    login_url = "planner:login"

    def _build_context(self, request, form=None):
        cards, connections = _build_user_dashboard(request.user)
        return {
            "form": form
            or CreatePlanForm(initial={"inviter_email": request.user.email}),
            "plan_cards": cards,
            "connections": connections,
        }

    def get(self, request):
        return render(request, self.template_name, self._build_context(request))

    def post(self, request):
        form = CreatePlanForm(request.POST)
        inviter_email = form.data.get("inviter_email", "").strip().lower()
        account_email = (request.user.email or "").strip().lower()
        if account_email and inviter_email and inviter_email != account_email:
            form.add_error("inviter_email", "Use the same email as your account.")

        if not form.is_valid():
            return render(
                request, self.template_name, self._build_context(request, form=form)
            )

        with transaction.atomic():
            plan = Plan.objects.create(
                created_by=request.user,
                inviter_email=form.cleaned_data["inviter_email"],
                invitee_email=form.cleaned_data["invitee_email"],
                city=form.cleaned_data["city"],
            )
            inviter = Participant.objects.create(
                plan=plan,
                user=request.user,
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
            Participant.objects.select_related("plan", "user"), token=token
        )
        participant = _claim_participant_for_user(request, participant)
        access_response = _enforce_participant_access(request, participant)
        if access_response:
            return access_response

        vote = _get_vote(participant)
        form = VoteForm(instance=vote)
        return render(
            request, self.template_name, {"form": form, "participant": participant}
        )

    def post(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan", "user"), token=token
        )
        participant = _claim_participant_for_user(request, participant)
        access_response = _enforce_participant_access(request, participant)
        if access_response:
            return access_response

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
            Participant.objects.select_related("plan", "user"), token=token
        )
        participant = _claim_participant_for_user(request, participant)
        access_response = _enforce_participant_access(request, participant)
        if access_response:
            return access_response

        context = self._build_context(request, participant)
        return render(request, self.template_name, context)

    def post(self, request, token):
        participant = get_object_or_404(
            Participant.objects.select_related("plan", "user"), token=token
        )
        participant = _claim_participant_for_user(request, participant)
        access_response = _enforce_participant_access(request, participant)
        if access_response:
            return access_response

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
