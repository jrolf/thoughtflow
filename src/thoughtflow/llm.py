"""
LLM class for ThoughtFlow.

A unified interface for calling various language model services.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error


class LLM:
    """
    The LLM class is designed to interface with various language model services.
    
    Attributes:
        service (str): The name of the service provider (e.g., 'openai', 'groq', 'anthropic').
        model (str): The specific model to be used within the service.
        api_key (str): The API key for authenticating requests.
        api_secret (str): The API secret for additional authentication.
        last_params (dict): Stores the parameters used in the last API call.

    Methods:
        __init__(model_id, key, secret):
            Initializes the LLM instance with a model ID, API key, and secret.
        
        call(msg_list, params):
            Calls the appropriate API based on the service with the given message list and parameters.
        
        _call_openai(msg_list, params):
            Sends a request to the OpenAI API with the specified messages and parameters.
        
        _call_groq(msg_list, params):
            Sends a request to the Groq API with the specified messages and parameters.
        
        _call_anthropic(msg_list, params):
            Sends a request to the Anthropic API with the specified messages and parameters.
        
        _send_request(url, data, headers):
            Helper function to send HTTP requests to the specified URL with data and headers.
    """
    def __init__(self, model_id='', key='API_KEY', secret='API_SECRET'):
        # Parse model ID and initialize service and model name
        if ':' not in model_id: model_id = 'openai:gpt-4-turbo'
        
        splitted = model_id.split(':') 
        self.service = splitted[0]
        self.model = ''.join(splitted[1:]) 
        self.api_key = key
        self.api_secret = secret
        self.last_params = {} 
        # Make the object directly callable
        self.__call__ = self.call

    def _normalize_messages(self, msg_list):
        """
        Accepts either:
        - list[str] -> converts to [{'role':'user','content': str}, ...]
        - list[dict] with 'role' and 'content' -> passes through unchanged
        - list[dict] with only 'content' -> assumes role='user'
        Returns: list[{'role': str, 'content': str or list[...]}]
        """
        norm = []
        for m in msg_list:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                norm.append({"role": role, "content": content})
            else:
                # treat as plain user text
                norm.append({"role": "user", "content": str(m)})
        return norm

    def call(self, msg_list, params={}):
        self.last_params = dict(params)
        # General function to call the appropriate API with msg_list and optional parameters
        if self.service == 'openai':
            return self._call_openai(msg_list, params)
        elif self.service == 'groq':
            return self._call_groq(msg_list, params)
        elif self.service == 'anthropic':
            return self._call_anthropic(msg_list, params)
        elif self.service == 'ollama':
            return self._call_ollama(msg_list, params)
        elif self.service == 'gemini':
            return self._call_gemini(msg_list, params)
        elif self.service == 'openrouter':
            return self._call_openrouter(msg_list, params)
        else:
            raise ValueError("Unsupported service '{}'.".format(self.service))

    def _call_openai(self, msg_list, params):
        url = "https://api.openai.com/v1/chat/completions"
        data = json.dumps({
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            **params
        }).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_groq(self, msg_list, params):
        url = "https://api.groq.com/openai/v1/chat/completions"
        data = json.dumps({
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            **params
        }).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Groq/Python 0.9.0",
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_anthropic(self, msg_list, params):
        url = "https://api.anthropic.com/v1/messages"
        data = json.dumps({
            "model": self.model,
            "max_tokens": params.get("max_tokens", 1024),
            "messages": self._normalize_messages(msg_list),
        }).encode("utf-8")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Anthropic returns {"content":[{"type":"text","text":"..."}], ...}
        choices = [c.get("text", "") for c in res.get("content", [])]
        return choices

    def _call_gemini(self, msg_list, params):
        """
        Calls Google Gemini/SVertexAI chat-supported models via REST API.
        Requires self.api_key to be set.
        """
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}".format(self.model, self.api_key)
        # Gemini expects a list of "contents" alternating user/assistant
        # We collapse the messages into a sequence of dicts as required by Gemini
        # Gemini wants [{"role": "user/assistant", "parts": [{"text": ...}]}]
        gemini_msgs = []
        for m in self._normalize_messages(msg_list):
            # Google's role scheme: "user" or "model"
            g_role = {"user": "user", "assistant": "model", "system": "user"}.get(m["role"], "user")
            gemini_msgs.append({
                "role": g_role,
                "parts": [{"text": str(m["content"])}] if isinstance(m["content"], str) else m["content"]
            })
        payload = {
            "contents": gemini_msgs,
            **{k: v for k, v in params.items() if k != "model"}
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Gemini returns { "candidates": [ { "content": { "parts": [ { "text": ... } ] } } ] }
        choices = []
        for cand in res.get("candidates", []):
            parts = cand.get("content", {}).get("parts", [])
            text = "".join([p.get("text", "") for p in parts])
            choices.append(text)
        return choices

    def _call_openrouter(self, msg_list, params):
        """
        Calls an LLM via the OpenRouter API. Requires self.api_key.
        API docs: https://openrouter.ai/docs
        Model list: https://openrouter.ai/docs#models
        """
        url = "https://openrouter.ai/api/v1/chat/completions"
        data = json.dumps({
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            **params
        }).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": params.get("referer", "https://your-app.com"),
            "X-Title": params.get("title", "Thoughtflow"),
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_ollama(self, msg_list, params):
        """
        Calls a local model served via Ollama (http://localhost:11434 by default).
        Expects no authentication. Ollama messages format is like OpenAI's.
        """
        base_url = params.get("ollama_url", "http://localhost:11434")
        url = base_url.rstrip('/') + "/api/chat"
        payload = {
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            "stream": False,  # Disable streaming to get a single JSON response
            **{k: v for k, v in params.items() if k not in ("ollama_url", "model")}
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Ollama returns {"message": {...}, ...} or {"choices": [{...}]}
        # Prefer OpenAI-style extraction if available, else fallback
        if "choices" in res:
            choices = [a["message"]["content"] for a in res.get("choices", [])]
        elif "message" in res:
            # single result
            msg = res["message"]
            choices = [msg.get("content", "")]
        elif "response" in res:
            # streaming/fallback
            choices = [res["response"]]
        else:
            choices = []
        return choices

    def _send_request(self, url, data, headers):
        # Sends the actual HTTP request and handles the response
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")  
                # Attempt to parse JSON response; handle plain-text responses
                try:
                    return json.loads(response_data)  # Parse JSON response
                except json.JSONDecodeError:
                    # If response is not JSON, return it as-is in a structured format
                    return {"error": "Non-JSON response", "response_data": response_data}
                
        except urllib.error.HTTPError as e:
            # Return the error details in case of an HTTP error
            error_msg = e.read().decode("utf-8")
            print("HTTP Error:", error_msg)  # Log HTTP error for debugging
            return {"error": json.loads(error_msg) if error_msg else "Unknown HTTP error"}
        except Exception as e:
            return {"error": str(e)}  
