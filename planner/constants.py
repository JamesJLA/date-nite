DEFAULT_VOTE_QUESTION_LABELS = {
    "dinner_choice": "What dinner vibe sounds best?",
    "activity_choice": "What should the main activity be?",
    "sweet_choice": "How do you want to end the night?",
    "budget_choice": "What budget level feels right?",
    "mood_choice": "What mood are you going for?",
    "duration_choice": "How long should the date be?",
    "transport_choice": "How much travel are you open to?",
    "dietary_notes": "Any dietary needs or foods to avoid?",
    "accessibility_notes": "Any accessibility preferences to plan around?",
}

DEFAULT_GENERATED_QUESTIONS = {
    "questions": [
        {
            "id": "dinner_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["dinner_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "italian", "label": "Cozy Italian spot"},
                {"value": "sushi", "label": "Sushi and candlelight"},
                {"value": "tapas", "label": "Tapas and shared plates"},
                {"value": "home", "label": "Cook a candlelit dinner at home"},
            ],
        },
        {
            "id": "activity_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["activity_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "movie", "label": "Rom-com movie night"},
                {"value": "music", "label": "Live music"},
                {"value": "art", "label": "Museum or art walk"},
                {"value": "dance", "label": "Dancing"},
            ],
        },
        {
            "id": "sweet_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["sweet_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "chocolate", "label": "Chocolate tasting"},
                {"value": "dessert", "label": "Dessert crawl"},
                {"value": "cocktail", "label": "Cocktails or mocktails"},
                {"value": "coffee", "label": "Late-night coffee date"},
            ],
        },
        {
            "id": "budget_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["budget_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "cozy", "label": "Budget-friendly and cozy"},
                {"value": "mid", "label": "Moderate splurge"},
                {"value": "fancy", "label": "Full romance splurge"},
            ],
        },
        {
            "id": "mood_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["mood_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "playful", "label": "Playful and light"},
                {"value": "classic", "label": "Classic romantic"},
                {"value": "adventurous", "label": "Adventurous"},
                {"value": "relaxed", "label": "Relaxed and low-key"},
            ],
        },
        {
            "id": "duration_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["duration_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "short", "label": "2-3 hours"},
                {"value": "half", "label": "Half evening"},
                {"value": "full", "label": "Full evening"},
            ],
        },
        {
            "id": "transport_choice",
            "text": DEFAULT_VOTE_QUESTION_LABELS["transport_choice"],
            "type": "single",
            "required": True,
            "options": [
                {"value": "walk", "label": "Walking or short rides"},
                {"value": "drive", "label": "Driving is fine"},
                {"value": "mixed", "label": "Mix of both"},
            ],
        },
        {
            "id": "dietary_notes",
            "text": DEFAULT_VOTE_QUESTION_LABELS["dietary_notes"],
            "type": "text",
            "required": False,
            "placeholder": "Any dietary needs or foods to avoid?",
        },
        {
            "id": "accessibility_notes",
            "text": DEFAULT_VOTE_QUESTION_LABELS["accessibility_notes"],
            "type": "text",
            "required": False,
            "placeholder": "Mobility, noise, or accessibility preferences",
        },
    ]
}
