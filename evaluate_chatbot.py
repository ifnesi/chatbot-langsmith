"""
Evaluate the RAG chatbot using LangSmith.

This script runs the chatbot against a test dataset and evaluates:
1. Answer relevance to the question
2. Groundedness in retrieved documents
3. Helpfulness and completeness
4. Appropriate handling of out-of-scope questions
"""

import logging

from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate

from utils.chatbot import RAGChatbot
from utils import set_logging_format, check_env_vars


# ============================================================================
# Evaluator Functions
# ============================================================================


def relevance_evaluator(run, example) -> dict:
    """
    Evaluate if the answer is relevant to the question.

    Checks if the answer addresses the user's question appropriately.
    """
    question = example.inputs.get("question", "")
    answer = run.outputs.get("answer", "")

    # Simple heuristic checks
    score = 0.0
    feedback = list()

    # Check 1: Answer is not empty
    if answer and len(answer.strip()) > 10:
        score += 0.3
    else:
        feedback.append("Answer is too short or empty")

    # Check 2: Answer is not a generic error message
    error_phrases = [
        "error",
        "failed",
        "unable to",
        "cannot process",
    ]
    if not any(phrase in answer.lower() for phrase in error_phrases):
        score += 0.3
    else:
        feedback.append("Answer contains error messages")

    # Check 3: Answer should mention CloudSync Pro for product questions
    if question and "cloudsync" not in question.lower():
        if "cloudsync" in answer.lower():
            score += 0.2
        else:
            feedback.append("Answer should mention CloudSync Pro")
    else:
        score += 0.2

    # Check 4: Reasonable length (not too verbose, not too short)
    word_count = len(answer.split())
    if 20 <= word_count <= 300:
        score += 0.2
    elif word_count > 300:
        feedback.append("Answer is too verbose")

    return {
        "key": "relevance",
        "score": score,
        "comment": "; ".join(feedback) if feedback else "Answer is relevant",
    }


def groundedness_evaluator(run) -> dict:
    """
    Evaluate if the answer is grounded in the retrieved sources.

    Checks if the answer uses information from the retrieved documents.
    """
    sources = run.outputs.get("sources", list())
    answer = run.outputs.get("answer", "")

    score = 0.0
    feedback = list()

    # Check 1: Sources were retrieved
    if sources and len(sources) > 0:
        score += 0.4
        feedback.append(f"Retrieved {len(sources)} sources")
    else:
        feedback.append("No sources retrieved")

    # Check 2: Answer doesn't make unsupported claims
    unsupported_phrases = [
        "i don't know",
        "i'm not sure",
        "i cannot find",
        "no information available",
    ]
    if any(phrase in answer.lower() for phrase in unsupported_phrases):
        feedback.append("Answer indicates lack of information")
    else:
        score += 0.3

    # Check 3: Answer isn't making up information
    # (This is a simple check - in production you'd use more sophisticated methods)
    suspicious_phrases = [
        "i think",
        "probably",
        "maybe",
        "might be",
    ]
    if not any(phrase in answer.lower() for phrase in suspicious_phrases):
        score += 0.3
    else:
        feedback.append("Answer contains uncertain language")

    return {
        "key": "groundedness",
        "score": score,
        "comment": "; ".join(feedback),
    }


def helpfulness_evaluator(run, example) -> dict:
    """
    Evaluate if the answer is helpful and complete.

    Checks if the answer provides actionable information.
    """
    answer = run.outputs.get("answer", "")
    expected_output = example.outputs or dict()
    should_mention = expected_output.get("should_mention", list())
    should_not_mention = expected_output.get("should_not_mention", list())

    score = 0.0
    feedback = list()

    answer_lower = answer.lower()

    # Check 1: Answer mentions expected keywords
    if should_mention:
        mentioned = sum(
            1 for keyword in should_mention if keyword.lower() in answer_lower
        )
        mention_ratio = mentioned / len(should_mention) if should_mention else 0
        score += mention_ratio * 0.5
        feedback.append(
            f"Mentioned {mentioned}/{len(should_mention)} expected keywords"
        )
    else:
        score += 0.5  # No specific requirements

    # Check 2: Answer avoids inappropriate keywords
    if should_not_mention:
        avoided = sum(
            1 for keyword in should_not_mention if keyword.lower() not in answer_lower
        )
        avoid_ratio = avoided / len(should_not_mention) if should_not_mention else 1
        score += avoid_ratio * 0.3
        if avoid_ratio < 1:
            feedback.append(f"Contains inappropriate keywords")
    else:
        score += 0.3

    # Check 3: Answer is actionable (contains steps, instructions, or clear information)
    actionable_indicators = [
        "step",
        "click",
        "go to",
        "select",
        "follow",
        "instructions",
    ]
    if any(indicator in answer_lower for indicator in actionable_indicators):
        score += 0.2
        feedback.append("Contains actionable information")
    else:
        # Not all answers need to be actionable (e.g., informational questions)
        score += 0.1

    return {
        "key": "helpfulness",
        "score": score,
        "comment": "; ".join(feedback),
    }


def scope_evaluator(run, example) -> dict:
    """
    Evaluate if out-of-scope questions are handled appropriately.

    Checks if the chatbot stays within CloudSync Pro support domain.
    """
    answer = run.outputs.get("answer", "")
    topic = example.outputs.get("topic", "")

    score = 1.0
    feedback = list()

    # For out-of-scope questions
    if topic == "out_of_scope":
        # Should politely decline and redirect to CloudSync topics
        decline_phrases = [
            "i can help you with cloudsync",
            "i'm here to help with cloudsync",
            "i specialize in cloudsync",
            "i can assist with cloudsync",
            "about cloudsync",
        ]

        if any(phrase in answer.lower() for phrase in decline_phrases):
            feedback.append("Appropriately handled out-of-scope question")
        else:
            score = 0.3
            feedback.append("Should redirect to CloudSync Pro topics")
    else:
        # For in-scope questions, shouldn't decline
        decline_phrases = [
            "i cannot",
            "i can't help",
            "out of my scope",
        ]
        if any(phrase in answer.lower() for phrase in decline_phrases):
            score = 0.3
            feedback.append("Incorrectly declined in-scope question")
        else:
            feedback.append("Appropriately handled in-scope question")

    return {
        "key": "scope_handling",
        "score": score,
        "comment": "; ".join(feedback),
    }


# ============================================================================
# Evaluation Target Function
# ============================================================================


def chatbot_pipeline(inputs: dict) -> dict:
    """
    Wrapper function for the chatbot to work with LangSmith evaluate().

    This function is called for each example in the dataset.
    Creates a fresh chatbot instance for each evaluation to avoid state.
    """
    question = inputs.get("question", "")

    # Create a fresh chatbot instance (no conversation history)
    chatbot = RAGChatbot(
        verbose=False,
        html_output=False,
    )

    # Get response
    response = chatbot.query(
        question,
        show_sources=True,
    )

    return {
        "answer": response["answer"],
        "sources": response["sources"],
        "question": question,
    }


# ============================================================================
# Main Evaluation Function
# ============================================================================


def run_evaluation(
    model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
    retriever_k: int = 3,
    dataset_name: str = "CloudSync Pro Support - RAG Evaluation",
    model_embeddings: str = "amazon.titan-embed-text-v2:0",
    experiment_prefix: str = "rag-chatbot-eval",
):
    """Run evaluation on the chatbot."""

    set_logging_format()
    load_dotenv()
    check_env_vars()

    logging.info("=" * 70)
    logging.info("🧪 Running Chatbot Evaluation")
    logging.info("=" * 70)

    # Initialize LangSmith client
    ls_client = Client()

    # Check if dataset exists
    try:
        datasets = list(ls_client.list_datasets(dataset_name=dataset_name))
        if not datasets:
            logging.error(f"❌ Dataset '{dataset_name}' not found")
            logging.info(
                "💡 Run 'python create_dataset.py' first to create the dataset"
            )
            return
    except Exception as e:
        logging.error(f"❌ Error accessing dataset: {e}")
        return

    logging.info(f"📊 Dataset: {dataset_name}")
    logging.info("🤖 Model: Claude 3 Haiku via AWS Bedrock")
    logging.info("🔍 Evaluators: Relevance, Groundedness, Helpfulness, Scope Handling")
    logging.info("=" * 70)

    # Define all evaluators
    evaluators = [
        relevance_evaluator,
        groundedness_evaluator,
        helpfulness_evaluator,
        scope_evaluator,
    ]

    # Run evaluation
    logging.info("⏳ Running evaluation (this may take a few minutes)...")

    try:
        results = evaluate(
            chatbot_pipeline,
            data=dataset_name,
            evaluators=evaluators,
            experiment_prefix=experiment_prefix,
            max_concurrency=2,  # Run 2 evaluations in parallel
            metadata={
                "model": model_id,
                "embeddings": model_embeddings,
                "retriever_k": retriever_k,
                "description": "RAG chatbot evaluation with multiple evaluators",
            },
        )

        logging.info("=" * 70)
        logging.info("✅ Evaluation Complete!")
        logging.info("=" * 70)
        logging.info("📊 Results Summary:")
        logging.info(f"  - Experiment: {getattr(results, 'experiment_name', 'N/A')}")
        logging.info("🔍 View detailed results at:")
        logging.info("   https://smith.langchain.com")
        logging.info("=" * 70)
        logging.info("💡 Tips:")
        logging.info("  - Compare multiple evaluation runs to track improvements")
        logging.info("  - Adjust prompts and re-run to see impact on scores")
        logging.info("  - Add more test examples for better coverage")
        logging.info("=" * 70)

    except Exception as e:
        logging.error(f"❌ Evaluation failed: {e}")
        logging.error("💡 Make sure:")
        logging.error("  1. Redis is running: docker compose up -d")
        logging.error("  2. Documents are loaded: python load_documents.py")
        logging.error("  3. LangSmith API key is set in .env")
        raise


if __name__ == "__main__":
    run_evaluation()
