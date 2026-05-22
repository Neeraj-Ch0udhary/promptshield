from sentence_transformers import CrossEncoder
import numpy as np


class OutputGuard:
    def __init__(
        self,
        model_name: str = "cross-encoder/nli-MiniLM2-L6-H768",
        entailment_threshold: float = 0.40,
        contradiction_threshold: float = 0.60,
        fallback_message: str = "I'm not confident in my answer. Please verify with a human expert.",
    ):
        self.model = CrossEncoder(model_name)
        self.entailment_threshold = entailment_threshold
        self.contradiction_threshold = contradiction_threshold
        self.fallback_message = fallback_message

    def check(self, response: str, sources: list[str]) -> dict:
        if not sources:
            return {
                "consistent":    True,
                "confidence":    1.0,
                "safe_response": response,
                "flagged":       False,
                "reason":        None,
            }

        sentences = [s.strip() for s in response.split(".") if s.strip()]
        sentence_results = []

        for sentence in sentences:
            pairs = [(source, sentence) for source in sources]
            scores = self.model.predict(pairs, apply_softmax=True)
            # columns: [contradiction, neutral, entailment]
            contradiction_scores = scores[:, 0]
            entailment_scores    = scores[:, 2]

            max_contradiction = float(contradiction_scores.max())
            max_entailment    = float(entailment_scores.max())

            sentence_results.append({
                "sentence":         sentence,
                "max_entailment":   round(max_entailment, 4),
                "max_contradiction": round(max_contradiction, 4),
                # flagged if it contradicts a source OR has no entailment support
                "flagged": (
                    max_contradiction > self.contradiction_threshold or
                    max_entailment < self.entailment_threshold
                )
            })

        any_flagged  = any(r["flagged"] for r in sentence_results)
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
        ("Correct response",      "The Eiffel Tower is in Paris and was built in 1889 by Gustave Eiffel"),
        ("Hallucinated response", "The Eiffel Tower is located in Berlin and was built in 1756 by Napoleon"),
        ("Partial hallucination", "The Eiffel Tower is in Paris but it was built in 1756"),
    ]

    print("--- OutputGuard Test ---\n")
    for name, response in tests:
        result = guard.check(response, source_docs)
        status = "✅ PASS" if result["consistent"] else "🚨 FLAGGED"
        print(f"Test — {name}")
        print(f"  {status}  |  Confidence: {result['confidence']}")
        for d in result["details"]:
            flag = "⚠" if d["flagged"] else "✓"
            print(f"  {flag} '{d['sentence'][:55]}'")
            print(f"    entailment={d['max_entailment']}  contradiction={d['max_contradiction']}")
        print(f"  Output: {result['safe_response'][:80]}")
        print()