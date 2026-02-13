from unittest.mock import patch

from django.test import TestCase

from planner.models import Participant, Plan, Vote
from planner.services import _build_local_itinerary, generate_date_plan


class ServicesTests(TestCase):
    def _create_plan_with_votes(self):
        plan = Plan.objects.create(
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
            city="Austin, TX",
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
        return plan

    def test_build_local_itinerary_waits_for_both_votes(self):
        plan = Plan.objects.create(
            inviter_email="inviter@example.com",
            invitee_email="invitee@example.com",
        )

        text = _build_local_itinerary(plan)

        self.assertIn("Waiting for both votes", text)

    @patch.dict("os.environ", {}, clear=True)
    def test_generate_date_plan_uses_local_fallback_when_no_keys(self):
        plan = self._create_plan_with_votes()

        text = generate_date_plan(plan)

        self.assertIn("Local fallback plan", text)
        self.assertIn("no AI key configured", text)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True)
    @patch("planner.services._gemini_generate", return_value="A generated story")
    def test_generate_date_plan_uses_gemini_when_available(self, gemini_generate):
        plan = self._create_plan_with_votes()

        text = generate_date_plan(plan, locale_hint="fr-FR")

        self.assertEqual(text, "A generated story")
        prompt = gemini_generate.call_args[0][0]
        self.assertIn("Locale preference: fr-FR", prompt)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-key"}, clear=True)
    @patch("planner.services._gemini_generate", side_effect=RuntimeError("quota"))
    def test_generate_date_plan_falls_back_to_local_when_gemini_fails(
        self,
        _gemini_generate,
    ):
        plan = self._create_plan_with_votes()

        text = generate_date_plan(plan)

        self.assertIn("Gemini quota exceeded", text)
