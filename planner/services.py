import os


def _fallback_summary(plan) -> str:
    votes = []
    for participant in plan.participants.all():
        vote = getattr(participant, "vote", None)
        if vote:
            votes.append(
                f"{participant.get_role_display()}: {vote.get_dinner_choice_display()}, "
                f"{vote.get_activity_choice_display()}, {vote.get_sweet_choice_display()}, "
                f"{vote.get_budget_choice_display()}"
            )
    joined_votes = " | ".join(votes) if votes else "No votes yet."
    return (
        "Gemini is not configured yet. Add GEMINI_API_KEY to generate an AI date plan. "
        f"Current choices: {joined_votes}"
    )


def generate_date_plan(plan) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_summary(plan)

    try:
        from google import genai
    except Exception:
        return _fallback_summary(plan)

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

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()
        return text or _fallback_summary(plan)
    except Exception:
        return _fallback_summary(plan)
