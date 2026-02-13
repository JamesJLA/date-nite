import importlib
import json
import os

from .forms import DEFAULT_VOTE_QUESTION_LABELS


def _collect_votes(plan):
    collected = []
    for participant in plan.participants.all():
        vote = getattr(participant, "vote", None)
        if vote:
            collected.append((participant, vote))
    return collected


def _build_local_itinerary(plan, note: str = "") -> str:
    votes = _collect_votes(plan)
    if len(votes) < 2:
        return "Waiting for both votes before creating a shared date plan."

    (_, first_vote), (_, second_vote) = votes[0], votes[1]

    dinner = first_vote.get_dinner_choice_display()
    if first_vote.dinner_choice != second_vote.dinner_choice:
        dinner = (
            f"Compromise dinner: {first_vote.get_dinner_choice_display()} "
            f"then {second_vote.get_dinner_choice_display()}"
        )

    activity = first_vote.get_activity_choice_display()
    if first_vote.activity_choice != second_vote.activity_choice:
        activity = (
            f"Main activity: {first_vote.get_activity_choice_display()} with a quick "
            f"stop for {second_vote.get_activity_choice_display().lower()}"
        )

    sweets = first_vote.get_sweet_choice_display()
    if first_vote.sweet_choice != second_vote.sweet_choice:
        sweets = (
            f"Sweet finish: {first_vote.get_sweet_choice_display()} + "
            f"{second_vote.get_sweet_choice_display()}"
        )

    budget = first_vote.get_budget_choice_display()
    if first_vote.budget_choice != second_vote.budget_choice:
        budget = "Budget: blend cozy picks with one moderate splurge"

    intro = "Local fallback plan (AI unavailable right now)."
    if note:
        intro = f"{intro} Reason: {note}"

    return "\n".join(
        [
            intro,
            f"- Start with: {dinner}",
            f"- Do: {activity}",
            "- Add a romantic touch: exchange one handwritten note each",
            f"- End with: {sweets}",
            f"- Keep it within: {budget}",
            "Close with a short walk and plan your next date before heading home.",
        ]
    )


def _normalize_gemini_error(exc: Exception) -> str:
    lowered = str(exc).lower()
    if "resource_exhausted" in lowered or "quota" in lowered or "429" in lowered:
        return "Gemini quota exceeded"
    if "api key" in lowered or "unauth" in lowered or "permission" in lowered:
        return "invalid Gemini API key or permissions"
    return "Gemini unavailable"


def _gemini_generate(prompt: str, api_key: str):
    genai = importlib.import_module("google.genai")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return (response.text or "").strip()


def _extract_json_object(text: str):
    if not text:
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def generate_vote_questions(plan, locale_hint: str = "en-US"):
    defaults = DEFAULT_VOTE_QUESTION_LABELS.copy()
    people = []
    for participant in plan.participants.all():
        description = (participant.ideal_date or "").strip()
        if description:
            people.append(
                f"- {participant.get_role_display()} ideal date: {description}"
            )

    if len(people) < 2:
        return defaults

    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        return defaults

    prompt = (
        "You are helping a couple plan one date night. "
        "Generate personalized question labels for a voting form. "
        "Return JSON only, no markdown, no commentary.\n"
        f"Locale preference: {locale_hint}\n"
        "Use concise, warm language. Keep each value under 90 characters.\n"
        "Required JSON keys exactly:\n"
        "dinner_choice, activity_choice, sweet_choice, budget_choice, mood_choice, "
        "duration_choice, transport_choice, dietary_notes, accessibility_notes\n\n"
        f"Couple descriptions:\n{'\n'.join(people)}"
    )

    try:
        text = _gemini_generate(prompt, gemini_api_key)
        parsed = _extract_json_object(text)
        if not parsed:
            return defaults

        normalized = defaults.copy()
        for key in defaults:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                normalized[key] = value.strip()
        return normalized
    except Exception:
        return defaults


def generate_date_plan(
    plan,
    locale_hint: str = "en-US",
    feedback: str = "",
    previous_summary: str = "",
) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    gemini_reason = ""

    vote_lines = []
    for participant in plan.participants.all():
        vote = getattr(participant, "vote", None)
        if vote:
            vote_lines.append(
                f"- {participant.get_role_display()} chose: "
                f"dinner={vote.get_dinner_choice_display()}, "
                f"activity={vote.get_activity_choice_display()}, "
                f"sweets={vote.get_sweet_choice_display()}, "
                f"budget={vote.get_budget_choice_display()}, "
                f"mood={vote.get_mood_choice_display()}, "
                f"duration={vote.get_duration_choice_display()}, "
                f"transport={vote.get_transport_choice_display()}, "
                f"dietary_notes={vote.dietary_notes or 'none'}, "
                f"accessibility_notes={vote.accessibility_notes or 'none'}"
            )

    city_hint = (plan.city or "").strip()
    locality_line = (
        f"Locality: {city_hint}. Tailor suggestions to places and vibes common in this area."
        if city_hint
        else "Locality: not provided. Keep suggestions broadly applicable."
    )
    prompt = (
        "You are a romantic date planner. Build one Valentines date-night story for a couple based on both votes. "
        "Write in the user's locale and language when possible.\n"
        f"Locale preference: {locale_hint}\n"
        f"{locality_line}\n\n"
        "Output format:\n"
        "- First line: one warm intro sentence\n"
        "- Then exactly 5 bullet points that are practical\n"
        "- Final line: one short closing sentence\n\n"
        f"Votes:\n{'\n'.join(vote_lines)}"
    )

    if previous_summary and feedback:
        prompt += (
            "\n\nPrevious plan:\n"
            f"{previous_summary}\n\n"
            "Refinement request from couple:\n"
            f"{feedback}\n\n"
            "Update the plan to reflect this feedback while keeping it practical and realistic."
        )

    if gemini_api_key:
        try:
            text = _gemini_generate(prompt, gemini_api_key)
            if text:
                return text
            gemini_reason = "Gemini empty response"
        except Exception as exc:
            gemini_reason = _normalize_gemini_error(exc)

    reasons = [reason for reason in [gemini_reason] if reason]
    if reasons:
        return _build_local_itinerary(plan, "; ".join(reasons))

    if gemini_api_key:
        return _build_local_itinerary(plan, "Gemini unavailable")
    return _build_local_itinerary(plan, "no AI key configured")
