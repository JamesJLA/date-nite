import copy
import importlib
import json
import os
import re

from .constants import DEFAULT_GENERATED_QUESTIONS
from .models import Vote


_NUMBERED_STEP_RE = re.compile(
    r"^\s*(?:\d+[\.)]|[ivxlcdm]+[\.)])\s+(.*)$", re.IGNORECASE
)


def _clean_line(line: str) -> str:
    cleaned = line.strip()
    if not cleaned:
        return ""
    cleaned = cleaned.lstrip("#").strip()
    if cleaned.startswith("**") and cleaned.endswith("**") and len(cleaned) > 4:
        cleaned = cleaned[2:-2].strip()
    return cleaned


def _strip_step_prefix(line: str) -> str:
    stripped = line.strip()
    for prefix in ("-", "*", "•"):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    numbered_match = _NUMBERED_STEP_RE.match(stripped)
    if numbered_match:
        return numbered_match.group(1).strip()
    return ""


def _clean_generated_plan(text: str) -> str:
    if not text:
        return ""

    raw_lines = [line for line in text.splitlines() if line.strip()]
    if not raw_lines:
        return ""
    if len(raw_lines) == 1:
        return _clean_line(raw_lines[0])

    lines = [_clean_line(line) for line in raw_lines]
    lines = [line for line in lines if line and line != "```"]
    if not lines:
        return ""

    intro = ""
    steps = []
    trailing = []
    reached_steps = False

    for line in lines:
        step = _strip_step_prefix(line)
        if step:
            reached_steps = True
            steps.append(step)
            continue
        if reached_steps:
            trailing.append(line)
        elif not intro:
            intro = line
        else:
            steps.append(line)

    if not intro and steps:
        intro = steps.pop(0)

    closing = " ".join(trailing).strip()
    if not steps and not closing:
        return intro or "\n".join(lines)

    pretty_lines = []
    if intro:
        pretty_lines.append(intro)
    pretty_lines.extend(f"- {step}" for step in steps[:5])
    if closing:
        pretty_lines.append(closing)
    return "\n".join(pretty_lines)


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


def _gemini_generate(prompt: str, api_key: str):
    genai = importlib.import_module("google.genai")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return (response.text or "").strip()


def _normalize_gemini_error(exc: Exception) -> str:
    lowered = str(exc).lower()
    if "resource_exhausted" in lowered or "quota" in lowered or "429" in lowered:
        return "Gemini quota exceeded"
    if "api key" in lowered or "unauth" in lowered or "permission" in lowered:
        return "invalid Gemini API key or permissions"
    return "Gemini unavailable"


def _normalize_schema(schema):
    default = copy.deepcopy(DEFAULT_GENERATED_QUESTIONS)
    if not isinstance(schema, dict):
        return default
    questions = schema.get("questions")
    if not isinstance(questions, list):
        return default

    default_by_id = {item["id"]: item for item in default["questions"]}
    normalized = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        question_id = item.get("id")
        if question_id not in default_by_id:
            continue
        base = copy.deepcopy(default_by_id[question_id])

        text = item.get("text")
        if isinstance(text, str) and text.strip():
            base["text"] = text.strip()

        if base.get("type") == "single":
            options = []
            if isinstance(item.get("options"), list):
                for raw_option in item["options"]:
                    if not isinstance(raw_option, dict):
                        continue
                    value = raw_option.get("value")
                    label = raw_option.get("label")
                    if isinstance(value, str) and isinstance(label, str):
                        if value.strip() and label.strip():
                            options.append(
                                {"value": value.strip(), "label": label.strip()}
                            )
            if len(options) >= 2:
                base["options"] = options[:5]

        if base.get("type") == "text":
            placeholder = item.get("placeholder")
            if isinstance(placeholder, str):
                base["placeholder"] = placeholder.strip()

        normalized.append(base)

    if len(normalized) != len(default["questions"]):
        return default
    return {"questions": normalized}


def generate_vote_questions(plan, locale_hint: str = "en-US"):
    default = copy.deepcopy(DEFAULT_GENERATED_QUESTIONS)
    people = []
    for participant in plan.participants.all():
        description = (participant.ideal_date or "").strip()
        if description:
            people.append(
                f"- {participant.get_role_display()} ideal date: {description}"
            )

    if len(people) < 2:
        return default

    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        return default

    prompt = (
        "You are helping a couple plan one date night. "
        "Generate personalized voting questions and answer options. "
        'Return JSON only with this shape: {"questions":[...]}\n'
        f"Locale preference: {locale_hint}\n"
        "Use exactly these ids in this order: dinner_choice, activity_choice, sweet_choice, budget_choice, mood_choice, duration_choice, transport_choice, dietary_notes, accessibility_notes.\n"
        "For single-choice ids, include 3-5 options with value and label.\n"
        "For text ids, keep type=text and include placeholder.\n\n"
        f"Couple descriptions:\n{'\n'.join(people)}"
    )

    try:
        parsed = _extract_json_object(_gemini_generate(prompt, gemini_api_key))
        return _normalize_schema(parsed)
    except Exception:
        return default


def _collect_answer_lines(plan):
    schema = _normalize_schema(plan.generated_questions)
    lines = []
    for participant in plan.participants.all():
        generated = getattr(participant, "generated_vote", None)
        answers = getattr(generated, "answers", None)
        if not answers:
            try:
                vote = participant.vote
                answers = {
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
            except Vote.DoesNotExist:
                answers = None
        if not answers:
            continue

        answer_parts = []
        for question in schema["questions"]:
            question_id = question["id"]
            value = answers.get(question_id)
            if value in (None, ""):
                continue

            display_value = str(value)
            if question.get("type") == "single":
                option_lookup = {
                    option["value"]: option["label"]
                    for option in question.get("options", [])
                }
                display_value = option_lookup.get(value, display_value)

            answer_parts.append(f"{question['text']}={display_value}")

        if answer_parts:
            lines.append(
                f"- {participant.get_role_display()} answered: "
                + "; ".join(answer_parts)
            )
    return lines


def _build_local_itinerary(plan, note: str = "") -> str:
    lines = _collect_answer_lines(plan)
    if len(lines) < 2:
        return "Waiting for both votes before creating a shared date plan."

    intro = "Local fallback plan (AI unavailable right now)."
    if note:
        intro = f"{intro} Reason: {note}"

    return _clean_generated_plan(
        "\n".join(
            [
                intro,
                "- Start with a low-pressure meetup to settle into the evening.",
                "- Pick dinner that best matches your shared food and budget preferences.",
                "- Do one activity that fits your overlap in mood and pace.",
                "- Add one personal romantic touch inspired by your descriptions.",
                "- End with a sweet stop and a calm ride or walk home.",
                "Close by choosing one thing to repeat on your next date.",
            ]
        )
    )


def generate_date_plan(
    plan,
    locale_hint: str = "en-US",
    feedback: str = "",
    previous_summary: str = "",
) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    gemini_reason = ""

    vote_lines = _collect_answer_lines(plan)
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
                return _clean_generated_plan(text)
            gemini_reason = "Gemini empty response"
        except Exception as exc:
            gemini_reason = _normalize_gemini_error(exc)

    reasons = [reason for reason in [gemini_reason] if reason]
    if reasons:
        return _build_local_itinerary(plan, "; ".join(reasons))

    if gemini_api_key:
        return _build_local_itinerary(plan, "Gemini unavailable")
    return _build_local_itinerary(plan, "no AI key configured")
