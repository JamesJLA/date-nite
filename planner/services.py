import importlib
import os
import json
import urllib.error
import urllib.request


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
        dinner = f"Compromise dinner: {first_vote.get_dinner_choice_display()} then {second_vote.get_dinner_choice_display()}"

    activity = first_vote.get_activity_choice_display()
    if first_vote.activity_choice != second_vote.activity_choice:
        activity = f"Main activity: {first_vote.get_activity_choice_display()} with a quick stop for {second_vote.get_activity_choice_display().lower()}"

    sweets = first_vote.get_sweet_choice_display()
    if first_vote.sweet_choice != second_vote.sweet_choice:
        sweets = f"Sweet finish: {first_vote.get_sweet_choice_display()} + {second_vote.get_sweet_choice_display()}"

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
            f"- Add a romantic touch: exchange one handwritten note each",
            f"- End with: {sweets}",
            f"- Keep it within: {budget}",
            "Close with a short walk and plan your next date before heading home.",
        ]
    )


def _normalize_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "resource_exhausted" in lowered or "quota" in lowered or "429" in lowered:
        return "Gemini quota exceeded"
    if "api key" in lowered or "unauth" in lowered or "permission" in lowered:
        return "invalid Gemini API key or permissions"
    return "Gemini unavailable"


def _normalize_openai_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "http 401" in lowered or "invalid_api_key" in lowered:
        return "OpenAI key is invalid"
    if "http 429" in lowered or "quota" in lowered or "insufficient_quota" in lowered:
        return "OpenAI quota exceeded"
    if "http 403" in lowered:
        return "OpenAI project/key has no permission"
    return "OpenAI unavailable"


def _normalize_snowflake_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "authentication" in lowered or "incorrect username or password" in lowered:
        return "Snowflake credentials are invalid"
    if (
        "insufficient" in lowered
        or "not authorized" in lowered
        or "permission" in lowered
    ):
        return "Snowflake role lacks Cortex permission"
    return "Snowflake unavailable"


def _gemini_generate(prompt: str, api_key: str):
    genai = importlib.import_module("google.genai")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return (response.text or "").strip()


def _openai_generate(prompt: str, api_key: str):
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a romantic, practical date planner.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.7,
    }
    request = urllib.request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {body}") from exc

    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def _snowflake_generate(prompt: str):
    snowflake_connector = importlib.import_module("snowflake.connector")
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    role = os.getenv("SNOWFLAKE_ROLE")
    model = os.getenv("SNOWFLAKE_CORTEX_MODEL", "llama3.1-70b")

    if not all([account, user, password, warehouse, database, schema]):
        raise RuntimeError("missing Snowflake environment variables")

    connection = snowflake_connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%(model)s, %(prompt)s)",
                {"model": model, "prompt": prompt},
            )
            row = cursor.fetchone()
            if not row:
                return ""
            return (row[0] or "").strip()
    finally:
        connection.close()


def generate_date_plan(plan) -> str:
    snowflake_ready = all(
        [
            os.getenv("SNOWFLAKE_ACCOUNT"),
            os.getenv("SNOWFLAKE_USER"),
            os.getenv("SNOWFLAKE_PASSWORD"),
            os.getenv("SNOWFLAKE_WAREHOUSE"),
            os.getenv("SNOWFLAKE_DATABASE"),
            os.getenv("SNOWFLAKE_SCHEMA"),
        ]
    )
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    snowflake_reason = ""
    openai_reason = ""
    gemini_reason = ""

    vote_lines = []
    for participant in plan.participants.all():
        vote = getattr(participant, "vote", None)
        if not vote:
            continue
        vote_lines.append(
            f"- {participant.get_role_display()} chose: dinner={vote.get_dinner_choice_display()}, "
            f"activity={vote.get_activity_choice_display()}, sweets={vote.get_sweet_choice_display()}, "
            f"budget={vote.get_budget_choice_display()}"
        )

    prompt = (
        "You are a romantic date planner. Build one concise Valentines date-night itinerary "
        "for a couple based on both votes. Keep it to 5 short bullet points and one closing line. "
        "Use a warm tone and practical suggestions.\n\n"
        f"Votes:\n{'\n'.join(vote_lines)}"
    )

    if snowflake_ready:
        try:
            text = _snowflake_generate(prompt)
            if text:
                return text
        except Exception as exc:
            snowflake_reason = _normalize_snowflake_error(exc)

    if openai_api_key:
        try:
            text = _openai_generate(prompt, openai_api_key)
            if text:
                return text
        except Exception as exc:
            openai_reason = _normalize_openai_error(exc)

    if gemini_api_key:
        try:
            text = _gemini_generate(prompt, gemini_api_key)
            if text:
                return text
        except Exception as exc:
            gemini_reason = _normalize_error(exc)

    reasons = [
        reason for reason in [snowflake_reason, openai_reason, gemini_reason] if reason
    ]
    if reasons:
        return _build_local_itinerary(plan, "; ".join(reasons))

    if snowflake_ready:
        return _build_local_itinerary(plan, "Snowflake unavailable")
    if openai_reason:
        return _build_local_itinerary(plan, openai_reason)
    if gemini_reason:
        return _build_local_itinerary(plan, gemini_reason)

    if openai_api_key:
        return _build_local_itinerary(plan, "OpenAI unavailable")

    return _build_local_itinerary(plan, "no AI key configured")
