"""
Create a LangSmith dataset for chatbot evaluation.

This script creates test examples based on the CloudSync Pro knowledge base.
Each example includes a user question and expected answer characteristics.
"""

import logging

from dotenv import load_dotenv
from langsmith import Client

from utils import set_logging_format, check_env_vars


def create_evaluation_dataset():
    """Create a dataset in LangSmith with evaluation examples."""

    set_logging_format()
    load_dotenv()
    check_env_vars()

    logging.info("=" * 70)
    logging.info("📊 Creating LangSmith Evaluation Dataset")
    logging.info("=" * 70)

    # Initialize LangSmith client
    ls_client = Client()

    # Dataset name
    dataset_name = "CloudSync Pro Support - RAG Evaluation"

    # Define test examples
    # Each example has:
    # - inputs: The user's question
    # - outputs: Reference answer or evaluation criteria
    examples = [
        {
            "inputs": {"question": "How do I reset my password?"},
            "outputs": {
                "reference_answer": "Password reset instructions involving the login page and 'Forgot Password' link",
                "should_mention": ["forgot password", "email", "reset link"],
                "topic": "account_management",
            },
        },
        {
            "inputs": {"question": "What are the pricing plans available?"},
            "outputs": {
                "reference_answer": "Information about different pricing tiers (Free, Professional, Enterprise)",
                "should_mention": ["free", "professional", "enterprise", "pricing"],
                "topic": "pricing",
            },
        },
        {
            "inputs": {"question": "My files are not syncing. What should I do?"},
            "outputs": {
                "reference_answer": "Troubleshooting steps for sync issues including connection check and app restart",
                "should_mention": ["connection", "restart", "sync", "troubleshooting"],
                "topic": "troubleshooting",
            },
        },
        {
            "inputs": {"question": "Is my data encrypted?"},
            "outputs": {
                "reference_answer": "Information about encryption (AES-256, in-transit and at-rest)",
                "should_mention": ["encrypt", "security", "aes"],
                "topic": "security",
            },
        },
        {
            "inputs": {"question": "What is the maximum file size I can upload?"},
            "outputs": {
                "reference_answer": "File size limits per plan tier",
                "should_mention": ["file size", "limit", "gb", "mb"],
                "topic": "limits",
            },
        },
        {
            "inputs": {"question": "How do I share files with my team?"},
            "outputs": {
                "reference_answer": "Instructions for file sharing and collaboration features",
                "should_mention": ["share", "team", "collaboration", "permission"],
                "topic": "collaboration",
            },
        },
        {
            "inputs": {"question": "Can I access my files offline?"},
            "outputs": {
                "reference_answer": "Information about offline access and sync capabilities",
                "should_mention": ["offline", "sync", "access"],
                "topic": "features",
            },
        },
        {
            "inputs": {"question": "How do I upgrade my account?"},
            "outputs": {
                "reference_answer": "Steps to upgrade subscription plan",
                "should_mention": ["upgrade", "account", "subscription", "plan"],
                "topic": "account_management",
            },
        },
        {
            "inputs": {"question": "What happens if I delete a file?"},
            "outputs": {
                "reference_answer": "Information about file deletion, trash, and recovery",
                "should_mention": ["delete", "trash", "recover", "restore"],
                "topic": "features",
            },
        },
        {
            "inputs": {
                "question": "Does CloudSync Pro support two-factor authentication?"
            },
            "outputs": {
                "reference_answer": "Information about 2FA and security features",
                "should_mention": ["two-factor", "2fa", "security", "authentication"],
                "topic": "security",
            },
        },
        {
            "inputs": {"question": "How many devices can I connect?"},
            "outputs": {
                "reference_answer": "Device limits per plan tier",
                "should_mention": ["device", "limit", "connect"],
                "topic": "limits",
            },
        },
        {
            "inputs": {
                "question": "I'm getting an error code 403. What does this mean?"
            },
            "outputs": {
                "reference_answer": "Explanation of error code 403 and troubleshooting steps",
                "should_mention": ["error", "403", "permission", "access"],
                "topic": "troubleshooting",
            },
        },
        {
            "inputs": {"question": "Can I restore a previous version of a file?"},
            "outputs": {
                "reference_answer": "Information about version history and file restoration",
                "should_mention": ["version", "history", "restore", "previous"],
                "topic": "features",
            },
        },
        {
            "inputs": {"question": "How do I cancel my subscription?"},
            "outputs": {
                "reference_answer": "Steps to cancel subscription with information about data retention",
                "should_mention": ["cancel", "subscription", "account"],
                "topic": "account_management",
            },
        },
        {
            "inputs": {"question": "What file types are supported?"},
            "outputs": {
                "reference_answer": "List of supported file types and formats",
                "should_mention": ["file type", "support", "format"],
                "topic": "features",
            },
        },
        # Edge cases and out-of-scope questions
        {
            "inputs": {"question": "What's the weather today?"},
            "outputs": {
                "reference_answer": "Polite decline - out of scope",
                "should_mention": ["cloudsync", "help", "support"],
                "should_not_mention": ["weather", "forecast", "temperature"],
                "topic": "out_of_scope",
            },
        },
        {
            "inputs": {"question": "Tell me a joke"},
            "outputs": {
                "reference_answer": "Polite decline - out of scope",
                "should_mention": ["cloudsync", "help", "support"],
                "should_not_mention": ["joke", "funny"],
                "topic": "out_of_scope",
            },
        },
        {
            "inputs": {"question": ""},
            "outputs": {
                "reference_answer": "Request for clarification",
                "should_mention": ["help", "question"],
                "topic": "invalid_input",
            },
        },
    ]

    # Check if dataset already exists
    try:
        existing_datasets = list(ls_client.list_datasets(dataset_name=dataset_name))
        if existing_datasets:
            logging.warning("⚠️  Dataset '%s' already exists", dataset_name)
            logging.info("Deleting existing dataset to create fresh version...")
            for dataset in existing_datasets:
                ls_client.delete_dataset(dataset_id=dataset.id)
                logging.info("✅ Deleted existing dataset")
    except Exception as e:
        logging.debug("No existing dataset found: %s", e)

    # Create new dataset
    logging.info("📝 Creating dataset: %s", dataset_name)
    dataset = ls_client.create_dataset(
        dataset_name=dataset_name,
        description="Evaluation dataset for CloudSync Pro RAG chatbot. "
        "Contains questions about product features, troubleshooting, "
        "pricing, security, and edge cases.",
    )
    logging.info(f"✅ Dataset created with ID: {dataset.id}")

    # Add examples to dataset
    logging.info(f"📥 Adding {len(examples)} examples to dataset...")
    ls_client.create_examples(
        dataset_id=dataset.id,
        inputs=[ex["inputs"] for ex in examples],
        outputs=[ex["outputs"] for ex in examples],
    )
    logging.info("✅ Added all examples to dataset")

    # Print summary
    logging.info("=" * 70)
    logging.info("📊 Dataset Summary")
    logging.info("=" * 70)
    logging.info(f"Name: {dataset_name}")
    logging.info(f"ID: {dataset.id}")
    logging.info(f"Total Examples: {len(examples)}")
    logging.info("")
    logging.info("Topic Distribution:")
    topics = dict()
    for ex in examples:
        topic = ex["outputs"]["topic"]
        topics[topic] = topics.get(topic, 0) + 1
    for topic, count in sorted(topics.items()):
        logging.info(f"  - {topic}: {count}")
    logging.info("=" * 70)
    logging.info("🔍 View dataset at: https://smith.langchain.com")
    logging.info("=" * 70)

    return dataset


if __name__ == "__main__":
    create_evaluation_dataset()
