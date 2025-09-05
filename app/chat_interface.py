import ollama
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage, AIMessage
from app.knowledge_base import KnowledgeBase
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatInterface:
    def __init__(self):
        self.knowledge_base = None
        self.kb_load_attempted = False
        self._kb_lock = threading.Lock()
        
        # Initialize memory with smaller window for faster loading
        self.memory = ConversationBufferWindowMemory(
            k=5,  # Reduced from 10 to 5 for faster access
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
    
    def _lazy_load_kb(self):
        """Lazy load knowledge base only when needed"""
        if not self.kb_load_attempted:
            with self._kb_lock:
                if not self.kb_load_attempted:  # Double-check pattern
                    try:
                        logger.info("Lazy loading knowledge base...")
                        self.knowledge_base = KnowledgeBase()
                        logger.info("Knowledge base loaded successfully")
                    except Exception as e:
                        logger.error(f"Knowledge base initialization failed: {str(e)}")
                        self.knowledge_base = None
                    finally:
                        self.kb_load_attempted = True
    
    def generate_response(self, user_input: str, model_name: str, uploaded_file=None) -> str:
        """Generate AI response using local LLM with optimizations"""
        try:
            start_time = time.time()
            logger.info(f"Processing user input: {user_input[:50]}...")
            
            # Fast path for simple queries without KB search
            if self._is_simple_query(user_input):
                logger.info("Using fast path for simple query")
                prompt = self._build_simple_prompt(user_input, uploaded_file)
                context = ""
            else:
                # Get context with timeout
                context = self._get_context_with_timeout(user_input, timeout=2)
                prompt = self._build_optimized_prompt(user_input, context, uploaded_file)
            
            logger.info(f"Context retrieval took: {time.time() - start_time:.2f}s")
            
            # Generate response with optimized settings
            ollama_start = time.time()
            response = self._call_ollama_optimized(model_name, prompt)
            logger.info(f"Ollama call took: {time.time() - ollama_start:.2f}s")
            
            if response.get('error'):
                return f"Sorry, I encountered an error: {response['error']}. Please try again."
            
            ai_response = response['message']['content']
            
            # Update memory asynchronously to avoid blocking
            threading.Thread(
                target=self._update_memory_async,
                args=(user_input, ai_response),
                daemon=True
            ).start()
            
            logger.info(f"Total response time: {time.time() - start_time:.2f}s")
            return ai_response
            
        except Exception as e:
            logger.error(f"Error in generate_response: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}. Please try again."
    
    def _is_simple_query(self, query: str) -> bool:
        """Determine if query is simple enough to skip KB search"""
        simple_indicators = [
            len(query.split()) <= 5,  # Very short queries
            any(greeting in query.lower() for greeting in ['hello', 'hi', 'thanks', 'thank you']),
            query.strip().endswith('?') and len(query) < 50  # Simple questions
        ]
        return any(simple_indicators)
    
    def _get_context_with_timeout(self, query: str, timeout: int = 2) -> str:
        """Get context with strict timeout"""
        try:
            # Lazy load KB
            self._lazy_load_kb()
            
            if not self.knowledge_base:
                return ""
            
            logger.info(f"Searching KB with {timeout}s timeout...")
            
            # Use ThreadPoolExecutor for hard timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.knowledge_base.search_relevant_content,
                    query,
                    2  # Limit results for speed
                )
                try:
                    result = future.result(timeout=timeout)
                    return result[:800] if result else ""  # Limit context size
                except FutureTimeoutError:
                    logger.warning(f"KB search timed out after {timeout}s")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error getting context: {str(e)}")
            return ""
    
    def _build_simple_prompt(self, user_input: str, uploaded_file=None) -> str:
        """Build minimal prompt for fast responses"""
        parts = [f"User Query: {user_input}"]
        
        if uploaded_file:
            parts.append("Note: User has uploaded a log file for analysis.")
        
        parts.append("Please provide a helpful and concise response.")
        return "\n\n".join(parts)
    
    def _build_optimized_prompt(self, user_input: str, context: str, uploaded_file=None) -> str:
        """Build optimized prompt with limited context"""
        parts = [f"User Query: {user_input}"]
        
        if context and len(context.strip()) > 10:
            # Truncate context aggressively for speed
            truncated_context = context[:500] + "..." if len(context) > 500 else context
            parts.append(f"Relevant Context:\n{truncated_context}")
        
        if uploaded_file:
            parts.append("Note: User has uploaded a log file for analysis.")
        
        # Skip conversation history for speed unless it's a follow-up
        if self._seems_like_followup(user_input):
            try:
                history = self._get_recent_history(max_exchanges=1)
                if history:
                    parts.append(f"Previous Context: {history}")
            except Exception as e:
                logger.warning(f"Error loading history: {str(e)}")
        
        parts.append("Please provide a helpful response based on the available context.")
        
        final_prompt = "\n\n".join(parts)
        
        # Hard limit on prompt size
        if len(final_prompt) > 1200:
            final_prompt = final_prompt[:1200] + "\n\n[Truncated for performance]"
        
        return final_prompt
    
    def _seems_like_followup(self, query: str) -> bool:
        """Check if query seems like a follow-up question"""
        followup_indicators = [
            'also', 'additionally', 'furthermore', 'moreover',
            'what about', 'how about', 'and', 'but',
            'continue', 'more', 'other', 'another'
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in followup_indicators)
    
    def _get_recent_history(self, max_exchanges: int = 1) -> str:
        """Get recent conversation history efficiently"""
        try:
            history = self.memory.load_memory_variables({})
            if not history or not history.get('history'):
                return ""
            
            recent_messages = history['history'][-max_exchanges*2:]  # Get last N exchanges
            formatted = []
            
            for msg in recent_messages:
                if isinstance(msg, HumanMessage):
                    content = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                    formatted.append(f"User: {content}")
                elif isinstance(msg, AIMessage):
                    content = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                    formatted.append(f"Assistant: {content}")
            
            return " | ".join(formatted)
        except Exception as e:
            logger.error(f"Error getting recent history: {str(e)}")
            return ""
    
    def _call_ollama_optimized(self, model_name: str, prompt: str) -> dict:
        """Call Ollama with optimized settings"""
        try:
            # Optimized options for faster response
            options = {
                'temperature': 0.1,  # Lower temperature for faster, more focused responses
                'top_p': 0.9,
                'num_predict': 512,  # Limit response length for speed
                'stop': ['\n\n\n', '---']  # Stop on excessive newlines
            }
            
            messages = [
                {'role': 'system', 'content': self.system_prompt},
                {'role': 'user', 'content': prompt}
            ]
            
            logger.info(f"Calling Ollama with model: {model_name}")
            
            # Use ThreadPoolExecutor for timeout control
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    ollama.chat,
                    model=model_name,
                    messages=messages,
                    options=options
                )
                try:
                    result = future.result(timeout=25)  # 25 second timeout
                    return result
                except FutureTimeoutError:
                    logger.error("Ollama call timed out")
                    return {"error": "Response timeout - please try a simpler query"}
                    
        except Exception as e:
            logger.error(f"Error calling Ollama: {str(e)}")
            return {"error": str(e)}
    
    def _update_memory_async(self, user_input: str, ai_response: str):
        """Update memory asynchronously to avoid blocking main thread"""
        try:
            self.memory.save_context(
                {"input": user_input},
                {"output": ai_response}
            )
            logger.info("Memory updated successfully")
        except Exception as e:
            logger.error(f"Error updating memory: {str(e)}")
    
    def test_ollama_connection(self) -> tuple[bool, str]:
        """Test Ollama connection and return status"""
        try:
            logger.info("Testing Ollama connection...")
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
    
    def clear_memory(self):
        """Clear conversation memory"""
        try:
            self.memory.clear()
            logger.info("Memory cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing memory: {str(e)}")
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        return {
            'kb_loaded': self.knowledge_base is not None,
            'memory_size': len(self.memory.load_memory_variables({}).get('history', [])),
            'kb_load_attempted': self.kb_load_attempted
        }