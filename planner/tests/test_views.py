from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from planner.models import Participant, Plan, Vote
from planner.views import _format_story


class FormatStoryTests(TestCase):
    def test_format_story_splits_intro_steps_and_closing(self):
        intro, steps, closing = _format_story(
            "A sweet intro\n- First stop\n- Second stop\nWrap up"
        )

        self.assertEqual(intro, "A sweet intro")
        self.assertEqual(steps, ["First stop", "Second stop"])
        self.assertEqual(closing, "Wrap up")

    def test_format_story_without_bullets_uses_first_line_as_intro(self):
        intro, steps, closing = _format_story("Intro\nStep one\nStep two")

        self.assertEqual(intro, "Intro")
        self.assertEqual(steps, ["Step one", "Step two"])
        self.assertEqual(closing, "")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PlannerViewTests(TestCase):
    def test_home_post_creates_plan_sends_email_and_redirects(self):
        response = self.client.post(
            reverse("planner:home"),
            {
                "inviter_email": "me@example.com",
                "invitee_email": "partner@example.com",
                "city": "Seattle, WA",
            },
        )

        self.assertEqual(response.status_code, 302)
        plan = Plan.objects.get(inviter_email="me@example.com")
        inviter = Participant.objects.get(plan=plan, role=Participant.INVITER)
        invitee = Participant.objects.get(plan=plan, role=Participant.INVITEE)

        self.assertRedirects(response, reverse("planner:vote", args=[inviter.token]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [invitee.email])

    def test_vote_post_saves_vote_and_clears_existing_ai_summary(self):
        plan = Plan.objects.create(
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            ai_summary="Old summary",
        )
        inviter = Participant.objects.create(
            plan=plan,
            email=plan.inviter_email,
            role=Participant.INVITER,
        )

        response = self.client.post(
            reverse("planner:vote", args=[inviter.token]),
            {
                "dinner_choice": "italian",
                "activity_choice": "movie",
                "sweet_choice": "dessert",
                "budget_choice": "mid",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Vote.objects.filter(participant=inviter).exists())
        plan.refresh_from_db()
        self.assertEqual(plan.ai_summary, "")

    @override_settings(ENABLE_AI=True)
    @patch("planner.views.generate_date_plan", return_value="Fresh AI plan")
    def test_results_post_generates_plan_when_both_participants_voted(
        self,
        generate_date_plan,
    ):
        plan = Plan.objects.create(
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
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
        Vote.objects.create(
            participant=inviter,
            dinner_choice="italian",
            activity_choice="movie",
            sweet_choice="dessert",
            budget_choice="mid",
        )
        Vote.objects.create(
            participant=invitee,
            dinner_choice="sushi",
            activity_choice="music",
            sweet_choice="coffee",
            budget_choice="cozy",
        )

        response = self.client.post(
            reverse("planner:results", args=[inviter.token]),
            HTTP_ACCEPT_LANGUAGE="es-MX,es;q=0.9,en;q=0.8",
        )

        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.ai_summary, "Fresh AI plan")
        generate_date_plan.assert_called_once_with(
            plan,
            locale_hint="es-MX,es;q=0.9,en;q=0.8",
        )
