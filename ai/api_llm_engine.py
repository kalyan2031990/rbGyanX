"""
API-Based LLM Engine for "Ask rbGyanX"
======================================

Replaces local LLM with API-based intelligent assistant.
Supports OpenAI, Anthropic Claude, and Google Gemini.

Author: rbGyanX Team
Version: 1.0.0
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

# API client imports
OPENAI_AVAILABLE = False
ANTHROPIC_AVAILABLE = False
GOOGLE_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    pass

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    pass


class APILLMEngine:
    """API-based LLM engine for Ask rbGyanX"""
    
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None):
        """
        Initialize API LLM engine
        
        Parameters
        ----------
        provider : str
            Provider name: 'openai', 'anthropic', or 'google'
        api_key : str, optional
            API key (if None, will try to load from config)
        """
        self.provider = provider.lower()
        self.api_key = api_key or self._load_api_key()
        self.conversation_history: List[Dict[str, str]] = []
        self.model = self._get_default_model()
        
        # Initialize client
        self.client = self._initialize_client()
    
    def _load_api_key(self) -> Optional[str]:
        """Load API key from config file - STEP 1: Robust loading with validation"""
        config_path = Path.home() / ".rbgyanx" / "api_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    api_key = config.get(self.provider, {}).get('api_key')
                    # STEP 1: Validate API key
                    if api_key and len(api_key) > 20:
                        return api_key
            except Exception:
                pass
        return None
    
    @staticmethod
    def load_openai_api_key() -> Optional[str]:
        """STEP 1: Helper function to load OpenAI API key"""
        config_path = Path.home() / ".rbgyanx" / "api_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    api_key = config.get('openai', {}).get('api_key')
                    if api_key and len(api_key) > 20:
                        return api_key
            except Exception:
                pass
        return None
    
    def _get_default_model(self) -> str:
        """Get default model for provider"""
        models = {
            'openai': 'gpt-4o-mini',
            'anthropic': 'claude-3-haiku-20240307',
            'google': 'gemini-pro'
        }
        return models.get(self.provider, 'gpt-4o-mini')
    
    def _initialize_client(self):
        """Initialize API client - STEP 2: Ensure client is properly initialized"""
        if not self.api_key:
            return None
        
        if self.provider == 'openai' and OPENAI_AVAILABLE:
            # STEP 2: Try both old and new API patterns
            try:
                # New API pattern (OpenAI v1.0+)
                from openai import OpenAI
                return OpenAI(api_key=self.api_key)
            except (ImportError, AttributeError):
                # Old API pattern (pre-v1.0)
                openai.api_key = self.api_key
                return openai
        elif self.provider == 'anthropic' and ANTHROPIC_AVAILABLE:
            return anthropic.Anthropic(api_key=self.api_key)
        elif self.provider == 'google' and GOOGLE_AVAILABLE:
            genai.configure(api_key=self.api_key)
            return genai
        else:
            return None
    
    def chat(self, message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send message to LLM API - STEP 5: With provenance logging
        
        Parameters
        ----------
        message : str
            User message
        context : dict, optional
            Additional context (analysis mode, errors, etc.)
        
        Returns
        -------
        dict
            Response with 'text', 'source', 'tokens_used'
        """
        # STEP 5: Log interaction to provenance
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Ask rbGyanX interaction: query_length={len(message)}, provider={self.provider}")
        
        if not self.client:
            error_msg = 'Error: API client not initialized. Please configure API key.'
            logger.error(f"API client not initialized for Ask rbGyanX")
            return {
                'text': error_msg,
                'source': 'error',
                'tokens_used': 0
            }
        
        # Build system prompt with rbGyanX context
        system_prompt = self._build_system_prompt(context)
        
        # Add context to conversation
        if context:
            context_msg = self._format_context(context)
            if context_msg:
                self.conversation_history.append({
                    'role': 'system',
                    'content': context_msg
                })
        
        # Add user message
        self.conversation_history.append({
            'role': 'user',
            'content': message
        })
        
        try:
            if self.provider == 'openai':
                response = self._call_openai(system_prompt)
            elif self.provider == 'anthropic':
                response = self._call_anthropic(system_prompt)
            elif self.provider == 'google':
                response = self._call_google(system_prompt)
            else:
                return {
                    'text': f'Error: Unsupported provider: {self.provider}',
                    'source': 'error',
                    'tokens_used': 0
                }
            
            # Add assistant response to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': response['text']
            })
            
            # STEP 5: Log successful interaction to provenance
            logger.info(f"Ask rbGyanX response: response_length={len(response['text'])}, tokens_used={response.get('tokens_used', 0)}")
            
            return response
            
        except Exception as e:
            error_msg = f'Error calling API: {str(e)}'
            # STEP 5: Log error to provenance
            logger.error(f"Ask rbGyanX API error: {str(e)}")
            return {
                'text': error_msg,
                'source': 'error',
                'tokens_used': 0
            }
    
    def _build_system_prompt(self, context: Optional[Dict] = None) -> str:
        """Build system prompt with rbGyanX context - STEP 3: Mode-aware personality"""
        # STEP 3: Use mode-aware system prompt from context if provided
        if context and context.get('system_prompt_override'):
            prompt = context['system_prompt_override']
        else:
            # Fallback to default prompt
            prompt = """You are Ask rbGyanX, an AI assistant for the rbGyanX radiobiology-guided clinical decision support framework.

Your role:
- Provide educational support in radiobiology, medical physics, and statistics
- Help users understand TCP (Tumor Control Probability) and NTCP (Normal Tissue Complication Probability) models
- Explain radiotherapy concepts and treatment plan evaluation
- Assist with software usage and troubleshooting
- Answer questions about radiobiological modeling and clinical decision support

Important guidelines:
- You do NOT access patient data or PHI
- You do NOT make clinical decisions
- You provide educational and explanatory information only
- Always emphasize that final clinical decisions remain with qualified healthcare professionals
- Be clear, accurate, and cite sources when possible

rbGyanX is a research tool for:
- TCP/NTCP analysis
- Treatment plan evaluation
- Radiobiological modeling
- Clinical decision support (not autonomous decision making)
"""
        
        if context:
            if context.get('analysis_mode'):
                prompt += f"\nCurrent analysis mode: {context['analysis_mode']}\n"
            if context.get('recent_errors'):
                prompt += f"\nRecent errors encountered: {len(context['recent_errors'])} error(s)\n"
            if context.get('workflow_state'):
                prompt += f"\nCurrent workflow state: {context['workflow_state']}\n"
        
        return prompt
    
    def _format_context(self, context: Dict) -> str:
        """Format context for LLM"""
        parts = []
        
        if context.get('recent_errors'):
            parts.append("Recent errors:")
            for error in context['recent_errors'][:3]:
                parts.append(f"  - {error}")
        
        if context.get('qa_warnings'):
            parts.append("QA warnings:")
            for warning in context['qa_warnings'][:3]:
                parts.append(f"  - {warning}")
        
        return "\n".join(parts) if parts else ""
    
    def _call_openai(self, system_prompt: str) -> Dict[str, Any]:
        """Call OpenAI API - STEP 2: Real API calls with mode-aware temperature"""
        import logging
        logger = logging.getLogger(__name__)
        
        messages = [{'role': 'system', 'content': system_prompt}]
        
        # Add conversation history (last 10 messages to avoid token limits)
        for msg in self.conversation_history[-10:]:
            if msg['role'] != 'system':
                messages.append(msg)
        
        # STEP 2: Debug logging
        logger.debug("API call started to OpenAI")
        
        try:
            # STEP 2: Ensure API client is actually called
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI library not available")
            
            if not self.api_key:
                raise ValueError("API key not configured")
            
            if not self.client:
                raise ValueError("API client not initialized")
            
            # STEP 2: Determine temperature based on mode (BASIC: 0.2-0.3, ADVANCED: 0.5)
            # For now, use moderate temperature; mode-aware prompt handles personality
            temperature = 0.5  # Can be made mode-aware if needed
            
            # STEP 2: Use proper API pattern based on client type
            # Try new API pattern first (OpenAI v1.0+)
            if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
                # New API pattern
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=800
                )
                response_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0
            else:
                # Old API pattern (fallback)
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=800
                )
                response_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens
            
            # STEP 2: Debug logging
            logger.debug(f"API response received from OpenAI: {len(response_text)} chars, {tokens_used} tokens")
            
            # STEP 4: Enforce explanation-only guardrails
            response_text = self._sanitize_response(response_text)
            
            return {
                'text': response_text,
                'source': 'openai',
                'tokens_used': tokens_used
            }
        except Exception as e:
            # STEP 2: Log error
            logger.error(f"API error occurred: {str(e)}")
            raise
    
    def _sanitize_response(self, text: str) -> str:
        """STEP 4: Remove or rephrase recommendation patterns"""
        forbidden_patterns = [
            ('you should', 'you may consider (but clinical decisions remain with healthcare professionals)'),
            ('recommended', 'described in literature'),
            ('best plan', 'plan with specific characteristics'),
            ('optimal dose', 'dose within a specified range'),
            ('I suggest', 'One approach described in research'),
            ('must', 'typically'),
            ('need to', 'may be considered')
        ]
        
        text_lower = text.lower()
        for pattern, replacement in forbidden_patterns:
            if pattern in text_lower:
                # Replace pattern contextually (simplified - full implementation would be more sophisticated)
                import re
                text = re.sub(re.escape(pattern), replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def _call_anthropic(self, system_prompt: str) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        messages = []
        
        # Add conversation history
        for msg in self.conversation_history[-10:]:
            if msg['role'] != 'system':
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=system_prompt,
            messages=messages
        )
        
        return {
            'text': response.content[0].text,
            'source': 'anthropic',
            'tokens_used': response.usage.input_tokens + response.usage.output_tokens
        }
    
    def _call_google(self, system_prompt: str) -> Dict[str, Any]:
        """Call Google Gemini API"""
        model = genai.GenerativeModel(self.model)
        
        # Build prompt with system message and conversation
        prompt_parts = [system_prompt]
        for msg in self.conversation_history[-10:]:
            if msg['role'] == 'user':
                prompt_parts.append(f"User: {msg['content']}")
            elif msg['role'] == 'assistant':
                prompt_parts.append(f"Assistant: {msg['content']}")
        
        response = model.generate_content("\n".join(prompt_parts))
        
        return {
            'text': response.text,
            'source': 'google',
            'tokens_used': response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        }
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


class AskrbGyanXDialog:
    """Dialog window for Ask rbGyanX with API-based LLM"""
    
    def __init__(self, parent, context: Optional[Dict] = None, mode_controller=None):
        """
        Initialize Ask rbGyanX dialog
        
        Parameters
        ----------
        parent : tk.Tk or tk.Toplevel
            Parent window
        context : dict, optional
            Context information (analysis mode, errors, etc.)
        mode_controller : ModeController, optional
            Mode controller for BASIC/ADVANCED personality
        """
        self.parent = parent
        self.context = context or {}
        self.mode_controller = mode_controller
        self.engine = None
        self.ai_integration = None
        
        # Initialize AI integration with personality based on mode
        self._initialize_ai_integration()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Ask rbGyanX — Your AI Assistant")
        self.dialog.geometry("900x700")
        self.dialog.minsize(700, 500)
        
        # STEP 1: Configure grid weights for proper expansion
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)
        
        # Check for API configuration
        if not self._check_api_config():
            self._show_config_dialog()
            return
        
        # Initialize engine
        self._initialize_engine()
        
        # Create UI
        self._create_ui()
    
    def _initialize_ai_integration(self):
        """Initialize AI integration with mode-aware personality"""
        try:
            from rbgyanx.logic.ai_integration import AskRbGyanXIntegration, AIPersonality
            
            # Determine personality based on mode
            if self.mode_controller and self.mode_controller.is_advanced():
                personality = AIPersonality.ADVANCED
            else:
                personality = AIPersonality.BASIC
            
            self.ai_integration = AskRbGyanXIntegration(personality=personality)
        except ImportError:
            # Fallback if AI integration module not available
            self.ai_integration = None
    
    def _check_api_config(self) -> bool:
        """Check if API key is configured"""
        config_path = Path.home() / ".rbgyanx" / "api_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    # Check if any provider has API key
                    for provider in ['openai', 'anthropic', 'google']:
                        if config.get(provider, {}).get('api_key'):
                            return True
            except Exception:
                pass
        return False
    
    def _show_config_dialog(self):
        """Show API key configuration dialog"""
        config_window = tk.Toplevel(self.dialog)
        config_window.title("Configure API Key")
        config_window.geometry("500x300")
        
        ttk.Label(config_window, text="API Key Configuration", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        ttk.Label(config_window, 
                 text="Select provider and enter API key:",
                 font=("Arial", 10)).pack(pady=5)
        
        provider_var = tk.StringVar(value="openai")
        provider_frame = ttk.Frame(config_window)
        provider_frame.pack(pady=10)
        
        ttk.Radiobutton(provider_frame, text="OpenAI", 
                       variable=provider_var, value="openai").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(provider_frame, text="Anthropic Claude", 
                       variable=provider_var, value="anthropic").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(provider_frame, text="Google Gemini", 
                       variable=provider_var, value="google").pack(side=tk.LEFT, padx=10)
        
        ttk.Label(config_window, text="API Key:").pack(pady=5)
        api_key_entry = ttk.Entry(config_window, width=50, show="*")
        api_key_entry.pack(pady=5)
        
        def save_config():
            provider = provider_var.get()
            api_key = api_key_entry.get().strip()
            
            if not api_key:
                messagebox.showerror("Error", "API key cannot be empty")
                return
            
            # Save to config file
            config_path = Path.home() / ".rbgyanx"
            config_path.mkdir(parents=True, exist_ok=True)
            
            config_file = config_path / "api_config.json"
            config = {}
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
            
            if provider not in config:
                config[provider] = {}
            config[provider]['api_key'] = api_key
            config[provider]['configured_at'] = datetime.now().isoformat()
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            messagebox.showinfo("Success", f"API key saved for {provider}")
            config_window.destroy()
            self._initialize_engine()
            self._create_ui()
        
        ttk.Button(config_window, text="Save", command=save_config).pack(pady=10)
        ttk.Button(config_window, text="Cancel", 
                  command=lambda: [config_window.destroy(), self.dialog.destroy()]).pack()
    
    def _initialize_engine(self):
        """Initialize LLM engine with configured API key"""
        # Try to load config
        config_path = Path.home() / ".rbgyanx" / "api_config.json"
        provider = "openai"  # Default
        
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    # Find first configured provider
                    for p in ['openai', 'anthropic', 'google']:
                        if config.get(p, {}).get('api_key'):
                            provider = p
                            break
            except Exception:
                pass
        
        self.engine = APILLMEngine(provider=provider)
    
    def _create_ui(self):
        """Create dialog UI - STEP 1: Fixed layout with scrolling"""
        # Main container with grid layout
        main_container = ttk.Frame(self.dialog)
        main_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        main_container.grid_rowconfigure(1, weight=1)  # Conversation area expands
        main_container.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ttk.Frame(main_container)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        header.grid_columnconfigure(0, weight=1)
        
        ttk.Label(header, text="Ask rbGyanX", 
                 font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w")
        
        # Mode indicator
        mode_text = "ADVANCED" if (self.mode_controller and self.mode_controller.is_advanced()) else "BASIC"
        mode_label = ttk.Label(header, text=f"Mode: {mode_text}", 
                              font=("Arial", 9, "italic"),
                              foreground="#E67E22" if mode_text == "ADVANCED" else "#3498DB")
        mode_label.grid(row=0, column=1, sticky="e", padx=10)
        
        provider_label = ttk.Label(header, text=f"Provider: {self.engine.provider if self.engine else 'Not configured'}")
        provider_label.grid(row=0, column=2, sticky="e")
        
        # Conversation area - STEP 1: Scrollable with both scrollbars
        conversation_frame = ttk.Frame(main_container)
        conversation_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        conversation_frame.grid_rowconfigure(0, weight=1)
        conversation_frame.grid_columnconfigure(0, weight=1)
        
        # Canvas for scrolling
        canvas = tk.Canvas(conversation_frame, highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(conversation_frame, orient="vertical", command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(conversation_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Scrollable frame
        scrollable_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Pack scrollbars and canvas
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        canvas.grid(row=0, column=0, sticky="nsew")
        
        # Conversation text inside scrollable frame - Use Text widget (canvas handles scrolling)
        self.conversation_text = tk.Text(
            scrollable_frame, 
            wrap=tk.WORD, 
            font=("Arial", 10),
            state=tk.DISABLED,
            width=80,
            height=25
        )
        self.conversation_text.pack(fill=tk.BOTH, expand=True)
        
        # Welcome message
        welcome = "Welcome to Ask rbGyanX!\n\n"
        welcome += "I can help you with:\n"
        welcome += "• Radiobiology concepts (TCP, NTCP)\n"
        welcome += "• Medical physics questions\n"
        welcome += "• Software usage and troubleshooting\n"
        welcome += "• Treatment plan evaluation\n\n"
        welcome += "Type your question below and press Enter or click 'Ask'.\n"
        welcome += "=" * 60 + "\n\n"
        
        self.conversation_text.config(state=tk.NORMAL)
        self.conversation_text.insert(tk.END, welcome)
        self.conversation_text.config(state=tk.DISABLED)
        
        # Input area - STEP 1: Always visible
        input_frame = ttk.Frame(main_container)
        input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Label(input_frame, text="Your question:").pack(anchor=tk.W)
        
        self.query_entry = scrolledtext.ScrolledText(
            input_frame,
            height=3,
            wrap=tk.WORD,
            font=("Arial", 10)
        )
        self.query_entry.pack(fill=tk.BOTH, expand=True, pady=5)
        self.query_entry.bind("<Return>", lambda e: self._ask_question())
        self.query_entry.focus()
        
        # Buttons - STEP 1: Always visible
        button_frame = ttk.Frame(main_container)
        button_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        
        ttk.Button(button_frame, text="Ask", 
                  command=self._ask_question).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", 
                  command=self._clear_conversation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Configure API", 
                  command=self._show_config_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", 
                  command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _ask_question(self):
        """Send question to LLM"""
        if not self.engine or not self.engine.client:
            messagebox.showerror("Error", "API not configured. Please configure API key first.")
            self._show_config_dialog()
            return
        
        question = self.query_entry.get("1.0", tk.END).strip()
        if not question:
            return
        
        # Clear input
        self.query_entry.delete("1.0", tk.END)
        
        # Add question to conversation
        self.conversation_text.config(state=tk.NORMAL)
        self.conversation_text.insert(tk.END, f"You: {question}\n\n")
        self.conversation_text.insert(tk.END, "Ask rbGyanX: Thinking...\n\n")
        self.conversation_text.see(tk.END)
        self.conversation_text.config(state=tk.DISABLED)
        
        # Process in background thread
        def process_query():
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                # STEP 2: Debug logging
                logger.debug(f"Processing query: {question[:50]}...")
                
                # STEP 3: Relax safety filters - validate query through AI integration
                if self.ai_integration:
                    from rbgyanx.logic.ai_integration import AIInteractionType
                    # Default to EXPLANATION, but allow analytical queries
                    interaction_type = AIInteractionType.EXPLANATION
                    if any(kw in question.lower() for kw in ['why', 'what causes', 'how does', 'explain']):
                        interaction_type = AIInteractionType.EXPLANATION
                    elif any(kw in question.lower() for kw in ['disagree', 'divergence', 'difference', 'compare']):
                        interaction_type = AIInteractionType.DIVERGENCE_ANALYSIS
                    elif any(kw in question.lower() for kw in ['uncertainty', 'error', 'variance', 'source']):
                        interaction_type = AIInteractionType.UNCERTAINTY_DISCUSSION
                    
                    # STEP 3: Only block if truly asking for action/recommendation
                    is_blocked = any(kw in question.lower() for kw in ['recommend', 'should i', 'which is better', 'optimize', 'choose'])
                    if is_blocked:
                        def show_blocked():
                            self.conversation_text.config(state=tk.NORMAL)
                            content = self.conversation_text.get("1.0", tk.END)
                            content = content.replace("Ask rbGyanX: Thinking...\n\n", "")
                            self.conversation_text.delete("1.0", tk.END)
                            self.conversation_text.insert("1.0", content)
                            self.conversation_text.insert(tk.END, 
                                f"Ask rbGyanX: This query was blocked because it requests a recommendation or action.\n"
                                f"Please rephrase as an analytical question (e.g., 'Why does this model behave this way?' or 'What causes disagreement between models?')\n\n")
                            self.conversation_text.insert(tk.END, "=" * 60 + "\n\n")
                            self.conversation_text.see(tk.END)
                            self.conversation_text.config(state=tk.DISABLED)
                        self.dialog.after(0, show_blocked)
                        return
                
                # STEP 3: Pass mode-aware system prompt via context
                enhanced_context = self.context.copy()
                if self.ai_integration:
                    # Build mode-aware system prompt using AI integration
                    enhanced_context['system_prompt_override'] = self.ai_integration.get_system_prompt()
                    enhanced_context['personality'] = self.ai_integration.personality.value
                
                response = self.engine.chat(question, context=enhanced_context)
                
                def update_ui():
                    self.conversation_text.config(state=tk.NORMAL)
                    # Remove "Thinking..." message
                    content = self.conversation_text.get("1.0", tk.END)
                    content = content.replace("Ask rbGyanX: Thinking...\n\n", "")
                    self.conversation_text.delete("1.0", tk.END)
                    self.conversation_text.insert("1.0", content)
                    
                    # Add response - STEP 2: Show response even if empty (for debugging)
                    response_text = response.get('text', 'No response received')
                    if not response_text or response_text.strip() == '':
                        response_text = "Error: Empty response received from API. Please check API connection and try again."
                    
                    self.conversation_text.insert(tk.END, f"Ask rbGyanX: {response_text}\n\n")
                    self.conversation_text.insert(tk.END, "=" * 60 + "\n\n")
                    self.conversation_text.see(tk.END)
                    self.conversation_text.config(state=tk.DISABLED)
                
                self.dialog.after(0, update_ui)
                
            except Exception as e:
                import traceback
                error_msg = str(e)
                error_trace = traceback.format_exc()
                logger.error(f"Error processing query: {error_msg}\n{error_trace}")
                
                def show_error():
                    self.conversation_text.config(state=tk.NORMAL)
                    content = self.conversation_text.get("1.0", tk.END)
                    content = content.replace("Ask rbGyanX: Thinking...\n\n", "")
                    self.conversation_text.delete("1.0", tk.END)
                    self.conversation_text.insert("1.0", content)
                    # STEP 2: Show visible error in UI
                    self.conversation_text.insert(tk.END, 
                        f"Error: {error_msg}\n"
                        f"This error has been logged. Please check API configuration and connection.\n\n")
                    self.conversation_text.insert(tk.END, "=" * 60 + "\n\n")
                    self.conversation_text.see(tk.END)
                    self.conversation_text.config(state=tk.DISABLED)
                
                self.dialog.after(0, show_error)
        
        thread = threading.Thread(target=process_query, daemon=True)
        thread.start()
    
    def _clear_conversation(self):
        """Clear conversation history"""
        if self.engine:
            self.engine.clear_history()
        
        self.conversation_text.config(state=tk.NORMAL)
        self.conversation_text.delete("1.0", tk.END)
        welcome = "Conversation cleared.\n\nType your question below.\n"
        welcome += "=" * 60 + "\n\n"
        self.conversation_text.insert(tk.END, welcome)
        self.conversation_text.config(state=tk.DISABLED)

