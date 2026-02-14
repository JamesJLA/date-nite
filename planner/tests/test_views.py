from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from planner.models import GeneratedVote, Participant, Plan
from planner.views import _format_story

User = get_user_model()


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


class PlannerViewTests(TestCase):
    def _create_plan_with_participants(self):
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
        return plan, inviter, invitee

    def _create_votes_for_both(self, inviter, invitee):
        GeneratedVote.objects.create(
            participant=inviter,
            answers={
                "dinner_choice": "italian",
                "activity_choice": "movie",
                "sweet_choice": "dessert",
                "budget_choice": "mid",
                "mood_choice": "classic",
                "duration_choice": "half",
                "transport_choice": "mixed",
                "dietary_notes": "",
                "accessibility_notes": "",
            },
        )
        GeneratedVote.objects.create(
            participant=invitee,
            answers={
                "dinner_choice": "sushi",
                "activity_choice": "music",
                "sweet_choice": "coffee",
                "budget_choice": "cozy",
                "mood_choice": "playful",
                "duration_choice": "short",
                "transport_choice": "walk",
                "dietary_notes": "",
                "accessibility_notes": "",
            },
        )

    def test_home_allows_guest_session(self):
        response = self.client.get(reverse("planner:home"))

        self.assertEqual(response.status_code, 200)

    def test_home_post_creates_plan_and_shows_share_actions(self):
        user = User.objects.create_user(
            username="me@example.com",
            email="me@example.com",
            password="test-pass-123",
        )
        self.client.force_login(user)

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

        vote_response = self.client.get(reverse("planner:vote", args=[inviter.token]))
        share_link = reverse("planner:vote", args=[invitee.token])
        self.assertContains(vote_response, "Share invite link with your partner")
        self.assertContains(vote_response, share_link)
        self.assertContains(vote_response, "Open Gmail draft")
        self.assertContains(vote_response, "mail.google.com/mail/?view=cm")

    def test_home_post_rejects_mismatched_inviter_email(self):
        user = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="test-pass-123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("planner:home"),
            {
                "inviter_email": "not-owner@example.com",
                "invitee_email": "partner@example.com",
                "city": "Seattle, WA",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Use the same email as your account")
        self.assertEqual(Plan.objects.count(), 0)

    def test_vote_post_saves_vote_and_clears_existing_ai_summary(self):
        plan = Plan.objects.create(
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            ai_summary="Old summary",
        )
        inviter = Participant.objects.create(
            plan=plan,
            email=plan.inviter_email,
            ideal_date="Dinner somewhere warm and cozy.",
            role=Participant.INVITER,
        )
        Participant.objects.create(
            plan=plan,
            email=plan.invitee_email,
            ideal_date="Chill evening with live music.",
            role=Participant.INVITEE,
        )

        response = self.client.post(
            reverse("planner:vote", args=[inviter.token]),
            {
                "dinner_choice": "italian",
                "activity_choice": "movie",
                "sweet_choice": "dessert",
                "budget_choice": "mid",
                "mood_choice": "classic",
                "duration_choice": "half",
                "transport_choice": "mixed",
                "dietary_notes": "",
                "accessibility_notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(GeneratedVote.objects.filter(participant=inviter).exists())
        plan.refresh_from_db()
        self.assertEqual(plan.ai_summary, "")

    def test_vote_get_first_visit_prompts_for_ideal_date(self):
        plan, inviter, _invitee = self._create_plan_with_participants()

        response = self.client.get(reverse("planner:vote", args=[inviter.token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Describe your ideal date night")
        self.assertContains(response, "Save my ideal date")

    def test_vote_post_saves_ideal_date_before_voting(self):
        _plan, inviter, _invitee = self._create_plan_with_participants()

        response = self.client.post(
            reverse("planner:vote", args=[inviter.token]),
            {
                "action": "describe",
                "ideal_date": "An intimate sushi dinner with a jazz bar after.",
            },
        )

        self.assertEqual(response.status_code, 302)
        inviter.refresh_from_db()
        self.assertEqual(
            inviter.ideal_date,
            "An intimate sushi dinner with a jazz bar after.",
        )
        self.assertFalse(GeneratedVote.objects.filter(participant=inviter).exists())

    def test_vote_post_requires_both_descriptions_before_vote_form_submits(self):
        _plan, inviter, invitee = self._create_plan_with_participants()
        inviter.ideal_date = "Playful date with tapas and dancing."
        inviter.save(update_fields=["ideal_date"])

        response = self.client.post(
            reverse("planner:vote", args=[inviter.token]),
            {
                "dinner_choice": "italian",
                "activity_choice": "movie",
                "sweet_choice": "dessert",
                "budget_choice": "mid",
                "mood_choice": "classic",
                "duration_choice": "half",
                "transport_choice": "mixed",
                "dietary_notes": "",
                "accessibility_notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(GeneratedVote.objects.filter(participant=inviter).exists())
        self.assertFalse((invitee.ideal_date or "").strip())

    def test_vote_get_claims_participant_for_matching_user_email(self):
        user = User.objects.create_user(
            username="inviter@example.com",
            email="inviter@example.com",
            password="test-pass-123",
        )
        plan, inviter, _invitee = self._create_plan_with_participants()
        self.client.force_login(user)

        response = self.client.get(reverse("planner:vote", args=[inviter.token]))

        self.assertEqual(response.status_code, 200)
        inviter.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(inviter.user_id, user.id)
        self.assertEqual(plan.created_by_id, user.id)

    def test_vote_get_redirects_to_login_for_claimed_invite_when_logged_out(self):
        owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="test-pass-123",
        )
        plan, inviter, _invitee = self._create_plan_with_participants()
        inviter.user = owner
        inviter.save(update_fields=["user"])

        response = self.client.get(reverse("planner:vote", args=[inviter.token]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("planner:login"), response.url)

    def test_vote_get_redirects_home_for_wrong_logged_in_user(self):
        owner = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="test-pass-123",
        )
        stranger = User.objects.create_user(
            username="stranger@example.com",
            email="stranger@example.com",
            password="test-pass-123",
        )
        _plan, inviter, _invitee = self._create_plan_with_participants()
        inviter.user = owner
        inviter.save(update_fields=["user"])
        self.client.force_login(stranger)

        response = self.client.get(reverse("planner:vote", args=[inviter.token]))

        self.assertRedirects(response, reverse("planner:home"))

    def test_vote_post_describe_clears_all_existing_votes_for_plan(self):
        _plan, inviter, invitee = self._create_plan_with_participants()
        inviter.ideal_date = "Dinner and dancing"
        inviter.save(update_fields=["ideal_date"])
        invitee.ideal_date = "Low-key music night"
        invitee.save(update_fields=["ideal_date"])
        self._create_votes_for_both(inviter, invitee)

        response = self.client.post(
            reverse("planner:vote", args=[inviter.token]),
            {
                "action": "describe",
                "ideal_date": "Updated ideal date with less travel.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(GeneratedVote.objects.count(), 0)

    @override_settings(ENABLE_AI=True)
    @patch("planner.views.generate_date_plan")
    def test_results_post_does_not_generate_until_both_votes_exist(
        self,
        generate_date_plan,
    ):
        plan, inviter, _invitee = self._create_plan_with_participants()
        GeneratedVote.objects.create(
            participant=inviter,
            answers={
                "dinner_choice": "italian",
                "activity_choice": "movie",
                "sweet_choice": "dessert",
                "budget_choice": "mid",
                "mood_choice": "classic",
                "duration_choice": "half",
                "transport_choice": "mixed",
                "dietary_notes": "",
                "accessibility_notes": "",
            },
        )

        response = self.client.post(reverse("planner:results", args=[inviter.token]))

        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.ai_summary, "")
        generate_date_plan.assert_not_called()

    @override_settings(ENABLE_AI=True)
    @patch("planner.views.generate_date_plan", return_value="Fresh AI plan")
    def test_results_post_generates_plan_when_both_participants_voted(
        self,
        generate_date_plan,
    ):
        plan, inviter, invitee = self._create_plan_with_participants()
        self._create_votes_for_both(inviter, invitee)

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

    @override_settings(ENABLE_AI=True)
    @patch("planner.views.generate_date_plan", return_value="Refined plan")
    def test_results_post_refine_uses_feedback_and_previous_summary(
        self,
        generate_date_plan,
    ):
        plan, inviter, invitee = self._create_plan_with_participants()
        self._create_votes_for_both(inviter, invitee)
        plan.ai_summary = "Initial plan"
        plan.save(update_fields=["ai_summary"])

        response = self.client.post(
            reverse("planner:results", args=[inviter.token]),
            data={"action": "refine", "feedback": "More relaxed pace"},
        )

        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.ai_summary, "Refined plan")
        generate_date_plan.assert_called_once_with(
            plan,
            locale_hint="en-US",
            feedback="More relaxed pace",
            previous_summary="Initial plan",
        )

    @override_settings(ENABLE_AI=True)
    @patch("planner.views.generate_date_plan")
    def test_results_post_refine_requires_existing_plan_before_refining(
        self,
        generate_date_plan,
    ):
        plan, inviter, invitee = self._create_plan_with_participants()
        self._create_votes_for_both(inviter, invitee)

        response = self.client.post(
            reverse("planner:results", args=[inviter.token]),
            data={"action": "refine", "feedback": "Use nearby places"},
        )

        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.ai_summary, "")
        generate_date_plan.assert_not_called()
