"""
RAG Chatbot using Redis Vector Store and AWS Bedrock (Claude Haiku)
Demonstrates LangSmith monitoring for prompt engineering, testing, and observability.
"""

import os
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv
from langsmith import traceable
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory

# Handle imports for both running as script and as module
try:
    from utils import VectorStoreUtils, set_logging_format, check_env_vars
except ImportError:
    # When running as script from utils directory
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils import VectorStoreUtils, set_logging_format, check_env_vars


def format_docs(docs):
    """Format retrieved documents into a string."""
    return "\n\n".join(
        f"Source {i+1}:\n{doc.page_content}" for i, doc in enumerate(docs)
    )


class RAGChatbot:
    """RAG Chatbot using Redis and AWS Bedrock with LangChain."""

    def __init__(
        self,
        verbose: bool = True,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        model_embeddings: str = "amazon.titan-embed-text-v2:0",
        index_name: str = "cloudsync_docs",
        model_temperature: float = 0.7,
        model_max_tokens: int = 1024,
        rag_search_chunks: int = 3,  # Retrieve top 3 most relevant chunks by default
        max_history_exchanges: int = 5,  # Keep last 5 exchanges (10 messages) by default
        html_output: bool = True,  # Whether to format output for HTML rendering
    ):
        """Initialize the RAG chatbot.

        Args:
            verbose: Whether to print verbose output
            model_embeddings: AWS Bedrock model for embeddings
            model_id: AWS Bedrock model ID
        """
        # Load environment variables
        load_dotenv()

        self.verbose = verbose
        logging.info("🚀 Initializing RAG Chatbot...")

        # Initialize conversation memory (keeps last 5 exchanges = 10 messages)
        logging.info("💾 Initializing conversation memory...")
        self.message_history = ChatMessageHistory()
        self.max_history_exchanges = max_history_exchanges

        # Initialize vector store utilities
        logging.info("📦 Initializing vector store utilities...")
        self.vector_utils = VectorStoreUtils(
            model_id=model_embeddings,
        )

        # Connect to Redis vector store
        logging.info("🔗 Connecting to Redis vector store...")
        try:
            self.vectorstore = self.vector_utils.connect_to_redis(index_name)
            # Create retriever
            self.retriever = self.vectorstore.as_retriever(
                search_kwargs={
                    "k": rag_search_chunks,
                }
            )
            logging.info("✅ Connected to Redis")
        except Exception as e:
            logging.error("❌ %s", e)
            raise

        # Initialize AWS Bedrock LLM
        logging.info("🤖 Initializing AWS Bedrock...")
        try:
            self.llm = ChatBedrock(
                model_id=model_id,
                region_name=os.getenv("AWS_REGION", "eu-central-1"),
                model_kwargs={
                    "temperature": model_temperature,
                    "max_tokens": model_max_tokens,
                },
            )
            logging.info("✅ Connected to AWS Bedrock")
        except Exception as e:
            logging.error("❌ Failed to connect to Bedrock: %s", e)
            logging.info("💡 Check your AWS credentials and region")
            raise

        # Create initial system prompt
        initial_system_prompt = """You are a helpful customer support assistant for CloudSync Pro, a cloud storage solution.

Use the following context from our documentation to answer the customer's question. If the context doesn't contain relevant information, say so politely and suggest contacting support.

Context from documentation:
{context}

Instructions:
- Be friendly, professional, and concise
- Provide specific details from the context when available
- If you mention technical steps, format them clearly
- If the context doesn't have the answer, admit it and suggest alternatives
- Always prioritize customer satisfaction and clarity in your responses"""

        if html_output:
            initial_system_prompt += "\n- Answer in a HTML ready format, using paragraphs, lists, and bold text where appropriate"

        # Create custom prompt template for RAG
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", initial_system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{question}"),
            ]
        )

        logging.info("✅ Chatbot ready!\n")

    def _generate_embedding(
        self,
        text: str,
    ):
        """Generate embedding for a text query.

        Args:
            text: The text to generate embeddings for

        Returns:
            List of floats representing the embedding vector
        """
        # Use the traceable method from VectorStoreUtils
        return self.vector_utils.generate_embedding(text)

    @traceable(
        name="retrieve_documents",
        run_type="retriever",
        tags=["rag", "retrieval"],
    )
    def _retrieve_documents(self, question: str):
        """Retrieve relevant documents from the vector store.

        Args:
            question: User's question to search for

        Returns:
            List of relevant documents
        """
        return self.retriever.invoke(question)

    @traceable(
        name="format_prompt",
        run_type="prompt",
        tags=["rag", "prompt"],
    )
    def _format_prompt(self, question: str, context: str):
        """Format the prompt with context and question.

        Args:
            question: User's question
            context: Retrieved context from documents

        Returns:
            Formatted messages ready for the LLM
        """
        # Get chat history (already windowed)
        chat_history = self.message_history.messages

        messages = self.prompt.format_messages(
            context=context,
            question=question,
            chat_history=chat_history,
        )
        return messages

    @traceable(
        name="call_llm",
        run_type="llm",
        tags=["rag", "llm"],
    )
    def _call_llm(self, messages):
        """Call the LLM with formatted messages.

        Args:
            messages: Formatted prompt messages

        Returns:
            LLM response
        """
        response = self.llm.invoke(messages)
        return response

    @traceable(
        name="chatbot_query",
        run_type="chain",
        tags=["rag", "chatbot"],
    )
    def query(
        self,
        question: str,
        show_sources: bool = True,
    ) -> dict:
        """Query the chatbot with a question.

        Args:
            question: User's question
            show_sources: Whether to show source documents

        Returns:
            Dictionary with answer and sources
        """
        # Step 1: Generate embedding for the query (for tracing purposes)
        _ = self._generate_embedding(question)

        # Step 2: Retrieve relevant documents
        docs = self._retrieve_documents(question)

        # Step 3: Format documents into context
        context = format_docs(docs)

        # Step 4: Format the prompt
        messages = self._format_prompt(question, context)

        # Step 5: Call the LLM
        llm_response = self._call_llm(messages)

        # Step 6: Parse the response
        answer = (
            llm_response.content
            if hasattr(llm_response, "content")
            else str(llm_response)
        )

        # Save to conversation memory
        self.message_history.add_user_message(question)
        self.message_history.add_ai_message(answer)

        # Implement windowing: keep only last N exchanges (2 messages per exchange)
        max_messages = self.max_history_exchanges * 2
        if len(self.message_history.messages) > max_messages:
            # Keep only the most recent messages
            self.message_history.messages = self.message_history.messages[
                -max_messages:
            ]

        response = {
            "question": question,
            "answer": answer,
            "sources": list(),
        }

        # Extract source information
        if show_sources and docs:
            for doc in docs:
                source_info = {
                    "content": doc.page_content,
                    "source": "Redis " + doc.metadata.get("id", "Unknown"),
                }
                response["sources"].append(source_info)

        return response

    def reset_conversation(self):
        """Reset the conversation history."""
        self.message_history.clear()
        logging.info("🔄 Conversation history cleared")

    def get_conversation_history(self):
        """Get the current conversation history.

        Returns:
            List of messages in the conversation history
        """
        return self.message_history.messages


def main():
    """Run the interactive chatbot."""
    set_logging_format()
    check_env_vars()

    logging.info("=" * 70)
    logging.info("💬 CloudSync Pro Support Chatbot")
    logging.info("=" * 70)
    logging.info("Powered by:")
    logging.info("  - Redis Vector Store (semantic search)")
    logging.info("  - AWS Bedrock Claude Haiku (Frankfurt)")
    logging.info("  - LangSmith (monitoring & tracing)")
    logging.info("=" * 70)

    try:
        # Initialize chatbot
        chatbot = RAGChatbot(
            verbose=True,
            html_output=False,
        )

        logging.info("💡 Tips:")
        logging.info("  - Type 'quit' or 'exit' to end the conversation")
        logging.info("  - Type 'clear' to reset conversation history")
        logging.info("  - Type 'help' for sample questions")
        logging.info(
            "🎯 LangSmith project: %s", os.getenv("LANGCHAIN_PROJECT", "default")
        )
        logging.info("🔍 View traces at: https://smith.langchain.com")
        logging.info("=" * 70)

        # Interactive loop
        while True:
            try:
                # Get user input
                print("")
                question = input("You: ").strip()

                if not question:
                    continue

                # Handle special commands
                if question.lower() in ["quit", "exit", "bye"]:
                    print(
                        "\n👋 Thanks for using CloudSync Pro Support. Goodbye!"
                    )
                    break

                if question.lower() == "clear":
                    chatbot.reset_conversation()
                    continue

                if question.lower() == "help":
                    print("\n📋 Sample questions you can ask:")
                    print("  - How do I reset my password?")
                    print("  - What are the pricing plans?")
                    print("  - My files are not syncing, what should I do?")
                    print("  - Is my data encrypted?")
                    print("  - What's the file size limit?")
                    continue

                # Query the chatbot
                print("\n🤔 Thinking...\n")
                response = chatbot.query(question, show_sources=True)

                # Display the answer
                print("\nBot: %s\n" % response["answer"])

                # Display sources (optional, for transparency)
                if response["sources"]:
                    print("📚 Sources consulted:")
                    for i, source in enumerate(response["sources"], 1):
                        source_file = os.path.basename(source["source"])
                        print("  %d. %s" % (i, source_file))

                print("-" * 70)

            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print("\n❌ Error: %s\n" % e)
                continue

    except Exception as e:
        logging.error("\n❌ Failed to initialize chatbot: %s", e)
        logging.info("\n💡 Troubleshooting:")
        logging.info("  1. Make sure Redis is running: docker compose up -d")
        logging.info("  2. Load documents first: python load_documents.py")
        logging.info("  3. Check your .env file has all required credentials")
        sys.exit(1)


if __name__ == "__main__":
    main()
