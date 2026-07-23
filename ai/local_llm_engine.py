"""
Local LLM Engine - "Ask rbGyanX" AI Assistant
============================================

Local AI assistant for educational and explanatory purposes.
NO internet access, NO PHI access, NO DVH data access.

Supports:
- GPT4All
- llama.cpp
- Mistral local
- Other local LLM backends

Author: rbGyanX Team
Version: 1.1.0
"""

import logging
from typing import Optional, Dict, List, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Try to import local LLM libraries
GPT4ALL_AVAILABLE = False
LLAMA_CPP_AVAILABLE = False
MISTRAL_AVAILABLE = False

try:
    import gpt4all
    GPT4ALL_AVAILABLE = True
except ImportError:
    pass

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    pass

try:
    # Mistral might use different import
    import mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    pass


class LocalLLMEngine:
    """
    Local LLM engine for educational AI assistant.
    
    Mandatory PHI Firewall:
    - Explicit block on DVH objects
    - Explicit block on patient metadata
    - Explicit block on clinical datasets
    - No pandas DataFrame access
    """
    
    def __init__(self, model_path: Optional[Path] = None, backend: str = 'auto'):
        """
        Initialize local LLM engine.
        
        Parameters
        ----------
        model_path : Path, optional
            Path to local model file
        backend : str
            Backend to use: 'gpt4all', 'llama_cpp', 'mistral', or 'auto'
        """
        self.model_path = model_path
        self.backend = backend
        self.model = None
        self.initialized = False
        
        # PHI firewall patterns
        self.phi_block_patterns = [
            'dvh', 'patient', 'mrn', 'medical record',
            'clinical data', 'dataset', 'dataframe',
            'pandas', 'pd.read', 'patient id', 'patientid'
        ]
        
        # Allowed knowledge domains
        self.allowed_domains = [
            'radiobiology', 'tcp', 'ntcp', 'dose response',
            'radiation therapy', 'medical physics', 'statistics',
            'machine learning theory', 'model parameters',
            'literature', 'references', 'equations'
        ]
    
    def initialize(self) -> bool:
        """
        Initialize the local LLM model.
        
        Returns
        -------
        bool
            True if initialized successfully, False otherwise
        """
        if self.initialized:
            return True
        
        # Auto-detect backend if not specified
        if self.backend == 'auto':
            if GPT4ALL_AVAILABLE:
                self.backend = 'gpt4all'
            elif LLAMA_CPP_AVAILABLE:
                self.backend = 'llama_cpp'
            elif MISTRAL_AVAILABLE:
                self.backend = 'mistral'
            else:
                logger.warning("No local LLM backend available")
                return False
        
        try:
            if self.backend == 'gpt4all' and GPT4ALL_AVAILABLE:
                if self.model_path and self.model_path.exists():
                    self.model = gpt4all.GPT4All(
                        model_name=self.model_path.name,
                        model_path=str(self.model_path.parent)
                    )
                else:
                    # Try to use default model
                    self.model = gpt4all.GPT4All()
                self.initialized = True
                logger.info("Initialized GPT4All backend")
                return True
            
            elif self.backend == 'llama_cpp' and LLAMA_CPP_AVAILABLE:
                if not self.model_path or not self.model_path.exists():
                    logger.error("Model path required for llama.cpp")
                    return False
                self.model = Llama(
                    model_path=str(self.model_path),
                    n_ctx=2048,
                    verbose=False
                )
                self.initialized = True
                logger.info("Initialized llama.cpp backend")
                return True
            
            elif self.backend == 'mistral' and MISTRAL_AVAILABLE:
                # Mistral initialization would go here
                logger.warning("Mistral backend not fully implemented")
                return False
            
            else:
                logger.warning(f"Backend {self.backend} not available")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing LLM: {e}")
            return False
    
    def _check_phi_firewall(self, query: str):
        """
        Check if query violates PHI firewall.
        
        Parameters
        ----------
        query : str
            User query
            
        Returns
        -------
        tuple
            (is_safe, error_message) where is_safe is bool and error_message is Optional[str]
        """
        query_lower = query.lower()
        
        # Check for PHI patterns
        for pattern in self.phi_block_patterns:
            if pattern in query_lower:
                return False, f"Query blocked: Contains restricted term '{pattern}'. This assistant cannot access patient data, DVH files, or clinical datasets."
        
        return True, None
    
    def _is_educational_query(self, query: str) -> bool:
        """
        Check if query is educational (allowed).
        
        Parameters
        ----------
        query : str
            User query
            
        Returns
        -------
        bool
            True if query is educational
        """
        query_lower = query.lower()
        
        # Check if query relates to allowed domains
        for domain in self.allowed_domains:
            if domain in query_lower:
                return True
        
        # Check for educational keywords
        educational_keywords = [
            'what is', 'explain', 'how does', 'what does',
            'meaning of', 'definition', 'theory', 'model',
            'parameter', 'equation', 'literature', 'reference'
        ]
        
        return any(keyword in query_lower for keyword in educational_keywords)
    
    def ask(
        self,
        query: str,
        context: Optional[str] = None,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Process a query through the local LLM.
        
        Parameters
        ----------
        query : str
            User query
        context : str, optional
            Additional context (must be educational, no PHI)
        max_tokens : int
            Maximum tokens in response
            
        Returns
        -------
        dict
            Response dictionary with 'answer', 'status', 'error'
        """
        # Check PHI firewall
        is_safe, error_msg = self._check_phi_firewall(query)
        if not is_safe:
            return {
                'answer': None,
                'status': 'blocked',
                'error': error_msg
            }
        
        # Check if query is educational
        if not self._is_educational_query(query):
            return {
                'answer': None,
                'status': 'blocked',
                'error': 'Query must be educational. This assistant can only answer questions about radiobiology theory, model parameters, statistics, and medical physics concepts.'
            }
        
        # Check context for PHI
        if context:
            is_safe, error_msg = self._check_phi_firewall(context)
            if not is_safe:
                return {
                    'answer': None,
                    'status': 'blocked',
                    'error': error_msg
                }
        
        # Initialize if needed
        if not self.initialized:
            if not self.initialize():
                return {
                    'answer': None,
                    'status': 'error',
                    'error': 'Local LLM model not available. Please install a local LLM backend (GPT4All, llama.cpp, or Mistral) and provide a model file.'
                }
        
        # Build prompt
        system_prompt = """You are an educational AI assistant for rbGyanX, a radiobiological analysis tool.
You can answer questions about:
- Radiobiology theory (TCP, NTCP models)
- Model parameters and their meanings
- Statistical concepts
- Medical physics principles
- Literature references

You CANNOT access:
- Patient data
- DVH files
- Clinical datasets
- Any patient identifiers

Keep responses educational and cite literature when possible."""

        full_prompt = f"{system_prompt}\n\nUser question: {query}"
        if context:
            full_prompt += f"\n\nContext: {context}"
        
        try:
            # Generate response based on backend
            if self.backend == 'gpt4all' and GPT4ALL_AVAILABLE:
                response = self.model.generate(
                    prompt=full_prompt,
                    max_tokens=max_tokens,
                    temp=0.7
                )
                answer = response.strip()
            
            elif self.backend == 'llama_cpp' and LLAMA_CPP_AVAILABLE:
                output = self.model(
                    full_prompt,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    stop=["User question:", "\n\n\n"]
                )
                answer = output['choices'][0]['text'].strip()
            
            else:
                return {
                    'answer': None,
                    'status': 'error',
                    'error': 'Backend not properly initialized'
                }
            
            return {
                'answer': answer,
                'status': 'success',
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                'answer': None,
                'status': 'error',
                'error': f'Error generating response: {str(e)}'
            }
    
    def is_available(self) -> bool:
        """
        Check if local LLM is available.
        
        Returns
        -------
        bool
            True if a local LLM backend is available
        """
        return GPT4ALL_AVAILABLE or LLAMA_CPP_AVAILABLE or MISTRAL_AVAILABLE
    
    def get_available_backends(self) -> List[str]:
        """
        Get list of available backends.
        
        Returns
        -------
        list
            List of available backend names
        """
        backends = []
        if GPT4ALL_AVAILABLE:
            backends.append('gpt4all')
        if LLAMA_CPP_AVAILABLE:
            backends.append('llama_cpp')
        if MISTRAL_AVAILABLE:
            backends.append('mistral')
        return backends


def create_ai_assistant(model_path: Optional[Path] = None) -> Optional[LocalLLMEngine]:
    """
    Factory function to create AI assistant.
    
    Parameters
    ----------
    model_path : Path, optional
        Path to local model file
        
    Returns
    -------
    LocalLLMEngine or None
        Initialized AI assistant or None if not available
    """
    engine = LocalLLMEngine(model_path=model_path)
    if engine.is_available():
        return engine
    return None

