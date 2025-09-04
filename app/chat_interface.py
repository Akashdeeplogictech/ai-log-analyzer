import ollama
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage, AIMessage
from app.knowledge_base import KnowledgeBase
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatInterface:
    def __init__(self):
        try:
            self.knowledge_base = KnowledgeBase()
            logger.info("Knowledge base initialized successfully")
        except Exception as e:
            logger.error(f"Knowledge base initialization failed: {str(e)}")
            self.knowledge_base = None
            
        self.memory = ConversationBufferWindowMemory(
            k=10,  # Remember last 10 exchanges
            return_messages=True
        )
        
        self.system_prompt = """
        You are an expert system administrator and log analysis specialist. 
        Your role is to help users analyze log files, identify issues, and provide 
        actionable solutions. You have access to a knowledge base of best practices,
        troubleshooting guides, and system documentation.
        
        When analyzing logs:
        1. Identify patterns and anomalies
        2. Explain the root causes of issues
        3. Provide specific, actionable recommendations
        4. Suggest preventive measures
        5. Reference relevant documentation when available
        
        Always be concise but thorough in your explanations.
        """
    
    def generate_response(self, user_input: str, model_name: str, uploaded_file=None) -> str:
        """Generate AI response using local LLM"""
        try:
            # Get relevant context from knowledge base
            context = self.knowledge_base.search_relevant_content(user_input)
            
            # Build prompt with context
            #prompt = self.test_basic_functionality()
            prompt = self.build_full_prompt(user_input, context, uploaded_file)
            
            # Generate response using Ollama
            response = ollama.chat(
                model=model_name,
                messages=[
                    {'role': 'system', 'content': self.system_prompt},
                    {'role': 'user', 'content': prompt}
                ]
            )
            
            ai_response = response['message']['content']
            
            # Update conversation memory
            self.memory.save_context(
                {"input": user_input},
                {"output": ai_response}
            )
            
            return ai_response
            
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}. Please try again."
    def search_knowledge_base_safe(self, query: str, timeout_seconds: int = 3) -> str:
        """Search knowledge base with timeout to prevent hanging"""
        if not self.knowledge_base:
            logger.warning("Knowledge base not available")
            return ""
        
        try:
            logger.info(f"Searching knowledge base for: {query[:50]}...")
            
            # Use ThreadPoolExecutor for timeout functionality
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.knowledge_base.search_relevant_content, 
                    query, 
                    3  # n_results
                )
                try:
                    result = future.result(timeout=timeout_seconds)
                    logger.info("Knowledge base search completed successfully")
                    return result if result else ""
                except FutureTimeoutError:
                    logger.warning(f"Knowledge base search timed out after {timeout_seconds}s")
                    return ""
                    
        except Exception as e:
            logger.error(f"Knowledge base search error: {str(e)}")
            return ""
    
    def test_ollama_connection(self) -> tuple[bool, str]:
        """Test Ollama connection and return status"""
        try:
            logger.info("Testing Ollama connection...")
            # Test basic connection first
            models_response = ollama.list()
            if not isinstance(models_response, dict) or 'models' not in models_response:
                return False, "Invalid response format from Ollama"
            
            available_models = [m.get('name', '') for m in models_response.get('models', [])]
            if not available_models:
                return False, "No models available in Ollama"
            
            logger.info(f"Ollama connection successful. Models: {available_models}")
            return True, f"Connected. Available models: {', '.join(available_models)}"
            
        except Exception as e:
            logger.error(f"Ollama connection test failed: {str(e)}")
            return False, f"Connection failed: {str(e)}"

    def call_ollama_with_timeout(self, model_name: str, messages: list, options: dict, timeout_seconds: int = 30) -> dict:
        """Call Ollama API with timeout protection"""
        try:
            logger.info(f"Calling Ollama with model: {model_name}, timeout: {timeout_seconds}s")
            
            # Use ThreadPoolExecutor for timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
              future = executor.submit(
                ollama.chat,  # Function to call
                model_name,  # Model name
                messages,    # List of messages
                options      # Options dictionary
              )
              try:
                result = future.result(timeout=timeout_seconds)
                return result
              except FutureTimeoutError:
                logger.warning("Ollama call timed out")
                return {"error": "Timeout"}
        except Exception as e:
          logger.error(f"Error calling Ollama: {str(e)}")
          return {"error": str(e)}
    
    def build_simple_prompt(self, user_input: str, context: str) -> str:
        """Build simplified prompt for manual input to prevent complexity issues"""
        try:
            prompt_parts = []
            
            # Always include the user query
            prompt_parts.append(f"User Query: {user_input}")
            
            # Add context only if it's meaningful and not too long
            if context and len(context.strip()) > 10:
                # Limit context size for manual input
                limited_context = context[:300] + "..." if len(context) > 300 else context
                prompt_parts.append(f"Relevant Context: {limited_context}")
            
            # Skip conversation history for manual input to keep it simple
            # This prevents potential memory loading issues
            
            prompt_parts.append("Please provide a helpful and concise response.")
            
            final_prompt = "\n\n".join(prompt_parts)
            
            # Ensure prompt isn't too long
            if len(final_prompt) > 1500:
                final_prompt = final_prompt[:1500] + "\n\n[Truncated]"
            
            return final_prompt
            
        except Exception as e:
            logger.error(f"Error building simple prompt: {str(e)}")
            # Fallback to absolute minimum
            return f"User Query: {user_input}\n\nPlease provide a helpful response."
    
    def build_full_prompt(self, user_input: str, context: str, uploaded_file=None) -> str:
        """Build comprehensive prompt for file analysis"""
        try:
            prompt_parts = []
            
            prompt_parts.append(f"User Query: {user_input}")
            
            if context and len(context.strip()) > 10:
                # Allow more context for file analysis
                limited_context = context[:1000] + "..." if len(context) > 1000 else context
                prompt_parts.append(f"Relevant Documentation:\n{limited_context}")
            
            if uploaded_file:
                prompt_parts.append("Note: User has uploaded a log file for analysis.")
            
            # Add conversation history for file analysis (but limit it)
            try:
                history = self.memory.load_memory_variables({})
                if history and history.get('history'):
                    prompt_parts.append("Previous Conversation:")
                    for msg in history['history'][-2:]:  # Only last 2 messages
                        if isinstance(msg, HumanMessage):
                            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            prompt_parts.append(f"User: {content}")
                        elif isinstance(msg, AIMessage):
                            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                            prompt_parts.append(f"Assistant: {content}")
            except Exception as e:
                logger.warning(f"Error loading conversation history: {str(e)}")
            
            prompt_parts.append("Please provide a helpful response based on the context and conversation history.")
            
            final_prompt = "\n\n".join(prompt_parts)
            
            # Limit total prompt size
            if len(final_prompt) > 2500:
                final_prompt = final_prompt[:2500] + "\n\n[Truncated for length]"
            
            return final_prompt
            
        except Exception as e:
            logger.error(f"Error building full prompt: {str(e)}")
            return f"User Query: {user_input}\n\nNote: User has uploaded a log file for analysis.\n\nPlease provide a helpful response."
    
    def clear_memory(self):
        """Clear conversation memory"""
        try:
            self.memory.clear()
            logger.info("Memory cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing memory: {str(e)}")
    
    def test_basic_functionality(self) -> dict:
        """Test basic functionality to identify issues"""
        results = {
            'knowledge_base': False,
            'memory': False,
            'ollama': False
        }
        
        # Test knowledge base
        try:
            if self.knowledge_base:
                test_result = self.search_knowledge_base_safe("test query", timeout_seconds=1)
                results['knowledge_base'] = True
        except Exception as e:
            logger.error(f"Knowledge base test failed: {str(e)}")
        
        # Test memory
        try:
            self.memory.load_memory_variables({})
            results['memory'] = True
        except Exception as e:
            logger.error(f"Memory test failed: {str(e)}")
        
        # Test Ollama
        try:
            models = ollama.list()
            results['ollama'] = len(models.get('models', [])) > 0
        except Exception as e:
            logger.error(f"Ollama test failed: {str(e)}")
        
        return results