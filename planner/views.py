"""View layer for invite, voting, and results flows."""

from collections.abc import Iterable
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import (
    CreatePlanForm,
    GeneratedVoteForm,
    IdealDateForm,
    RefinePlanForm,
    SignUpForm,
)
from .models import GeneratedVote, Participant, Plan, Vote
from .services import generate_date_plan, generate_vote_questions


SESSION_TOKEN_KEY = "planner_tokens"
INVITE_EMAIL_SUBJECT = "You have a Date Nite invite"
INVITE_EMAIL_BODY_PREFIX = (
    "Your partner invited you to plan a date night. Open this link to vote: "
)
INVITE_CREATED_MESSAGE = (
    "Invite created. Share the partner link below by email, message, or copy/paste."
)


def _normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _count_voted(participants: Iterable[Participant]) -> int:
    return sum(1 for person in participants if _get_answers(person))


def _plan_card(plan, my_token, partner, participants):
    voted_count = _count_voted(participants)
    return {
        "plan": plan,
        "my_token": my_token,
        "partner": partner,
        "voted_count": voted_count,
        "all_voted": voted_count == len(participants),
    }


def _add_connection(connections, partner_key, partner_name, plan):
    item = connections.get(partner_key)
    if item is None:
        connections[partner_key] = {
            "name": partner_name,
            "count": 1,
            "last_plan": plan,
        }
        return

    item["count"] += 1
    if plan.created_at > item["last_plan"].created_at:
        item["last_plan"] = plan


def _sorted_connections(connections):
    return sorted(
        connections.values(),
        key=lambda entry: entry["last_plan"].created_at,
        reverse=True,
    )


def _load_accessible_participant(request, token):
    participant = get_object_or_404(
        Participant.objects.select_related("plan", "user"), token=token
    )
    _remember_session_token(request, participant.token)
    participant = _claim_participant_for_user(request, participant)
    access_response = _enforce_participant_access(request, participant)
    if access_response:
        return None, access_response
    return participant, None


def _invitee_vote_link(request, plan):
    invitee = plan.participants.filter(role=Participant.INVITEE).first()
    if not invitee:
        return ""
    return request.build_absolute_uri(
        reverse("planner:vote", kwargs={"token": invitee.token})
    )


def _invite_gmail_link(invitee_email, invitee_link):
    if not invitee_link or not invitee_email:
        return ""
    recipient = quote(invitee_email.strip())
    subject = quote(INVITE_EMAIL_SUBJECT)
    body = quote(f"{INVITE_EMAIL_BODY_PREFIX}{invitee_link}")
    return (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&to={recipient}&su={subject}&body={body}"
    )


def _legacy_vote_answers(vote):
    return {
        "dinner_choice": vote.dinner_choice,
        "activity_choice": vote.activity_choice,
        "sweet_choice": vote.sweet_choice,
        "budget_choice": vote.budget_choice,
        "mood_choice": vote.mood_choice,
        "duration_choice": vote.duration_choice,
        "transport_choice": vote.transport_choice,
        "dietary_notes": vote.dietary_notes,
        "accessibility_notes": vote.accessibility_notes,
    }


def _get_answers(participant):
    try:
        return participant.generated_vote.answers
    except GeneratedVote.DoesNotExist:
        pass

    try:
        return _legacy_vote_answers(participant.vote)
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
    if _normalize_email(request.user.email) != _normalize_email(participant.email):
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
    if request.user.is_authenticated and request.user.pk == participant.user_id:
        return None
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to access your saved date invite.")
        return redirect(f"{reverse('planner:login')}?next={request.get_full_path()}")
    messages.error(request, "That invite belongs to a different account.")
    return redirect("planner:home")


def _session_tokens(request):
    tokens = request.session.get(SESSION_TOKEN_KEY, [])
    return tokens if isinstance(tokens, list) else []


def _remember_session_token(request, token):
    token_value = str(token)
    tokens = _session_tokens(request)
    if token_value not in tokens:
        request.session[SESSION_TOKEN_KEY] = [token_value] + tokens[:19]


def _build_session_dashboard(request):
    tokens = _session_tokens(request)
    if not tokens:
        return [], []

    participants = (
        Participant.objects.filter(token__in=tokens)
        .select_related("plan", "user")
        .prefetch_related(
            "plan__participants__generated_vote",
            "plan__participants__vote",
            "plan__participants__user",
        )
    )

    cards = []
    connections = {}
    seen_plan_ids = set()

    for my_participant in participants:
        plan = my_participant.plan
        if plan.id in seen_plan_ids:
            continue
        seen_plan_ids.add(plan.id)

        all_people = list(plan.participants.all())
        partner = next(
            (person for person in all_people if person.id != my_participant.id), None
        )
        if not partner:
            continue

        cards.append(_plan_card(plan, my_participant.token, partner, all_people))

        partner_key = _normalize_email(partner.email)
        _add_connection(connections, partner_key, partner.email, plan)

    sorted_connections = _sorted_connections(connections)
    cards.sort(key=lambda item: item["plan"].created_at, reverse=True)
    return cards, sorted_connections


def _build_user_dashboard(user):
    plans = (
        Plan.objects.filter(participants__user=user)
        .distinct()
        .prefetch_related(
            "participants__generated_vote",
            "participants__vote",
            "participants__user",
        )
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

        cards.append(_plan_card(plan, my_participant.token, partner, participants))

        partner_key = _normalize_email(partner.email)
        partner_name = partner.email
        if partner.user_id:
            partner_name = partner.user.email or partner.user.username
        _add_connection(connections, partner_key, partner_name, plan)

    sorted_connections = _sorted_connections(connections)
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


class HomeView(View):
    template_name = "planner/home.html"

    def _build_context(self, request, form=None):
        if request.user.is_authenticated:
            cards, connections = _build_user_dashboard(request.user)
            initial_inviter_email = request.user.email
        else:
            cards, connections = _build_session_dashboard(request)
            initial_inviter_email = ""

        return {
            "form": form
            or CreatePlanForm(initial={"inviter_email": initial_inviter_email}),
            "plan_cards": cards,
            "connections": connections,
        }

    def get(self, request):
        return render(request, self.template_name, self._build_context(request))

    def post(self, request):
        form = CreatePlanForm(request.POST)
        inviter_email = _normalize_email(form.data.get("inviter_email"))
        account_email = (
            _normalize_email(request.user.email)
            if request.user.is_authenticated
            else ""
        )
        if account_email and inviter_email and inviter_email != account_email:
            form.add_error("inviter_email", "Use the same email as your account.")

        if not form.is_valid():
            return render(
                request, self.template_name, self._build_context(request, form=form)
            )

        with transaction.atomic():
            plan = Plan.objects.create(
                created_by=request.user if request.user.is_authenticated else None,
                inviter_email=form.cleaned_data["inviter_email"],
                invitee_email=form.cleaned_data["invitee_email"],
                city=form.cleaned_data["city"],
            )
            inviter = Participant.objects.create(
                plan=plan,
                user=request.user if request.user.is_authenticated else None,
                email=plan.inviter_email,
                role=Participant.INVITER,
            )
            Participant.objects.create(
                plan=plan,
                email=plan.invitee_email,
                role=Participant.INVITEE,
            )

        messages.success(request, INVITE_CREATED_MESSAGE)
        _remember_session_token(request, inviter.token)
        return redirect("planner:vote", token=inviter.token)


class VoteView(View):
    template_name = "planner/vote.html"

    @staticmethod
    def _all_descriptions_submitted(plan):
        participants = list(plan.participants.all())
        return participants and all(
            (person.ideal_date or "").strip() for person in participants
        )

    def _build_vote_context(
        self, request, participant, vote_form=None, ideal_form=None
    ):
        plan = participant.plan
        invitee_link = ""
        invite_gmail_link = ""
        if participant.role == Participant.INVITER:
            invitee_link = _invitee_vote_link(request, plan)
            invite_gmail_link = _invite_gmail_link(plan.invitee_email, invitee_link)

        descriptions_ready = self._all_descriptions_submitted(plan)

        has_schema = isinstance(plan.generated_questions, dict) and bool(
            plan.generated_questions.get("questions")
        )
        if descriptions_ready and not has_schema:
            locale_hint = request.headers.get("Accept-Language", "en-US")
            plan.generated_questions = generate_vote_questions(
                plan, locale_hint=locale_hint
            )
            plan.save(update_fields=["generated_questions"])

        if not (participant.ideal_date or "").strip():
            return {
                "participant": participant,
                "stage": "describe",
                "ideal_form": ideal_form or IdealDateForm(),
                "invitee_link": invitee_link,
                "invite_gmail_link": invite_gmail_link,
            }

        if not descriptions_ready:
            return {
                "participant": participant,
                "stage": "waiting",
                "ideal_form": ideal_form
                or IdealDateForm(initial={"ideal_date": participant.ideal_date}),
                "invitee_link": invitee_link,
                "invite_gmail_link": invite_gmail_link,
            }

        existing_vote = getattr(participant, "generated_vote", None)
        return {
            "participant": participant,
            "stage": "vote",
            "form": vote_form
            or GeneratedVoteForm(
                questions_schema=plan.generated_questions,
                initial_answers=getattr(existing_vote, "answers", None),
            ),
            "invitee_link": invitee_link,
            "invite_gmail_link": invite_gmail_link,
        }

    def get(self, request, token):
        participant, access_response = _load_accessible_participant(request, token)
        if access_response:
            return access_response

        context = self._build_vote_context(request, participant)
        return render(request, self.template_name, context)

    def post(self, request, token):
        participant, access_response = _load_accessible_participant(request, token)
        if access_response:
            return access_response

        action = request.POST.get("action", "vote")
        if action == "describe":
            ideal_form = IdealDateForm(request.POST)
            if not ideal_form.is_valid():
                context = self._build_vote_context(
                    request, participant, ideal_form=ideal_form
                )
                return render(request, self.template_name, context)

            participant.ideal_date = ideal_form.cleaned_data["ideal_date"].strip()
            participant.save(update_fields=["ideal_date"])
            plan = participant.plan
            participant_ids = list(plan.participants.values_list("id", flat=True))
            GeneratedVote.objects.filter(participant_id__in=participant_ids).delete()
            Vote.objects.filter(participant_id__in=participant_ids).delete()
            plan.generated_questions = {}
            plan.ai_summary = ""
            plan.save(update_fields=["generated_questions", "ai_summary"])
            messages.success(
                request, "Saved. Once both descriptions are in, your questions unlock."
            )
            return redirect("planner:vote", token=participant.token)

        if not self._all_descriptions_submitted(participant.plan):
            messages.warning(
                request,
                "Both people need to describe their ideal date before voting starts.",
            )
            return redirect("planner:vote", token=participant.token)

        form = GeneratedVoteForm(
            request.POST,
            questions_schema=participant.plan.generated_questions,
        )
        if not form.is_valid():
            context = self._build_vote_context(request, participant, vote_form=form)
            return render(request, self.template_name, context)

        GeneratedVote.objects.update_or_create(
            participant=participant,
            defaults={"answers": form.cleaned_answers()},
        )
        if participant.plan.ai_summary:
            participant.plan.ai_summary = ""
            participant.plan.save(update_fields=["ai_summary"])
        messages.success(request, "Your choices are saved.")
        return redirect("planner:results", token=participant.token)


class ResultsView(View):
    template_name = "planner/results.html"

    @staticmethod
    def _answer_rows(plan, answers):
        rows = []
        schema = (plan.generated_questions or {}).get("questions", [])
        for question in schema:
            question_id = question.get("id")
            if not question_id:
                continue
            value = (answers or {}).get(question_id)
            if value in (None, ""):
                continue

            display_value = value
            if question.get("type") == "single":
                option_map = {
                    option.get("value"): option.get("label")
                    for option in question.get("options", [])
                }
                display_value = option_map.get(value, value)

            rows.append(
                {
                    "question": question.get("text", question_id),
                    "answer": display_value,
                }
            )
        return rows

    def _build_context(self, request, participant):
        plan = participant.plan
        participants = plan.participants.all()

        participant_votes = []
        for person in participants:
            answers = _get_answers(person)
            participant_votes.append(
                {
                    "person": person,
                    "answers": answers,
                    "rows": self._answer_rows(plan, answers),
                }
            )

        all_voted = all(item["answers"] is not None for item in participant_votes)
        invitee_link = _invitee_vote_link(request, plan)

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
        participant, access_response = _load_accessible_participant(request, token)
        if access_response:
            return access_response

        context = self._build_context(request, participant)
        return render(request, self.template_name, context)

    def post(self, request, token):
        participant, access_response = _load_accessible_participant(request, token)
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
