from sentence_transformers import CrossEncoder
import numpy as np


class OutputGuard:
    def __init__(
        self,
        model_name: str = "cross-encoder/nli-MiniLM2-L6-H768",
        net_score_threshold: float = 0.10,
        fallback_message: str = "I'm not confident in my answer. Please verify with a human expert.",
    ):
        self.model = CrossEncoder(model_name)
        self.net_score_threshold = net_score_threshold
        self.fallback_message = fallback_message

    def check(self, response: str, sources: list[str]) -> dict:
        if not sources:
            return {
                "consistent":    True,
                "confidence":    1.0,
                "safe_response": response,
                "flagged":       False,
                "details":       [],
            }

        sentences = [s.strip() for s in response.split(".") if s.strip()]
        sentence_results = []

        for sentence in sentences:
            pairs = [(source, sentence) for source in sources]
            scores = self.model.predict(pairs, apply_softmax=True)

            entailment_scores    = scores[:, 2]
            contradiction_scores = scores[:, 0]

            max_entailment    = float(entailment_scores.max())
            max_contradiction = float(contradiction_scores.max())

            # Net score: high entailment AND low contradiction = trustworthy
            # Low net score = model is confused = likely hallucination
            net_score = max_entailment - max_contradiction
            flagged = net_score < self.net_score_threshold

            sentence_results.append({
                "sentence":          sentence,
                "max_entailment":    round(max_entailment, 4),
                "max_contradiction": round(max_contradiction, 4),
                "net_score":         round(net_score, 4),
                "flagged":           flagged
            })

        any_flagged    = any(r["flagged"] for r in sentence_results)
        avg_entailment = round(
            sum(r["max_entailment"] for r in sentence_results) / len(sentence_results), 4
        )

        return {
            "consistent":    not any_flagged,
            "confidence":    avg_entailment,
            "flagged":       any_flagged,
            "safe_response": self.fallback_message if any_flagged else response,
            "details":       sentence_results,
        }


if __name__ == "__main__":
    guard = OutputGuard()

    source_docs = [
        "The Eiffel Tower is located in Paris, France. It was built in 1889.",
        "The tower stands 330 metres tall and is made of iron.",
        "It was designed by engineer Gustave Eiffel.",
    ]

    tests = [
        ("Correct",      "The Eiffel Tower is in Paris and was built in 1889 by Gustave Eiffel"),
        ("Hallucinated", "The Eiffel Tower is located in Berlin and was built in 1756 by Napoleon"),
        ("Partial",      "The Eiffel Tower is in Paris but it was built in 1756"),
    ]

    print("--- OutputGuard Test ---\n")
    for name, response in tests:
        result = guard.check(response, source_docs)
        status = "✅ PASS" if result["consistent"] else "🚨 FLAGGED"
        print(f"{name}: {status}")
        for d in result["details"]:
            print(f"  entailment={d['max_entailment']}  contradiction={d['max_contradiction']}  net={d['net_score']}  flagged={d['flagged']}")
        print()