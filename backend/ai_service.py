import google.generativeai as genai
from config import config

class AIService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GOOGLE_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None

    async def analyze_code(self, diff_text: str):
        if not self.model:
            return "AI model not configured. Please provide a GOOGLE_API_KEY."
        
        prompt = f"""
        You are an expert software engineer and code reviewer. 
        Analyze the following GitHub Pull Request diff and provide constructive feedback.
        Focus on:
        1. Potential bugs or logical errors.
        2. Security vulnerabilities.
        3. Code quality and best practices (clean code, SOLID principles).
        4. Performance improvements.
        
        Provide the response in a clear, formatted style using Markdown.
        
        DIFF:
        {diff_text}
        """
        
        response = self.model.generate_content(prompt)
        return response.text
