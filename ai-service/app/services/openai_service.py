import sys
sys.path.insert(0, '/app')

from typing import Optional
from openai import AsyncOpenAI
from app.config import settings
from shared.database import async_session
from shared.models_db import AIPrompt
from sqlalchemy import select
import structlog

logger = structlog.get_logger()

class OpenAIService:
    DEFAULT_SYSTEM_PROMPT = """You are an experienced freelancer specializing in web development, design, and digital services. Write a professional, personalized cover letter for a project on Upwork.

Guidelines:
- Start with a strong hook that shows you understand the client's needs
- Highlight relevant experience and specific skills that match the project
- Keep it concise (150-250 words)
- Show enthusiasm without being pushy
- Include a soft call to action
- Use a friendly but professional tone
- Avoid generic phrases and templates
- Address the client's specific pain points mentioned in the project description

Format your response as a ready-to-send message without subject line."""

    STYLE_ANALYSIS_PROMPT = """Analyze the following text and extract the writing style characteristics:
- Tone (formal/casual/mix)
- Sentence structure (short/long/varied)
- Vocabulary level
- Use of personal pronouns
- Persuasion techniques used
- Common phrases or expressions

Text to analyze:
{text}

Provide a brief summary of the style that can be used as a guide for similar writing."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    @staticmethod
    async def generate(
        user_id: int,
        project_title: str,
        project_description: str,
        additional_context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        style_example: Optional[str] = None
    ) -> str:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        system_message = system_prompt or OpenAIService.DEFAULT_SYSTEM_PROMPT
        
        if style_example:
            system_message += f"\n\nWriting style reference:\n{style_example[:500]}"
        
        user_message = f"""Project Title: {project_title}

Project Description:
{project_description}"""
        
        if additional_context:
            user_message += f"\n\nAdditional Context:\n{additional_context}"
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            cover_letter = response.choices[0].message.content.strip()
            
            logger.info(
                "cover_letter_generated",
                user_id=user_id,
                title_length=len(project_title),
                response_length=len(cover_letter)
            )
            
            return cover_letter
            
        except Exception as e:
            logger.error("generation_error", user_id=user_id, error=str(e))
            raise
    
    @staticmethod
    async def get_prompt(user_id: int) -> dict:
        async with async_session() as db:
            result = await db.execute(
                select(AIPrompt).where(AIPrompt.user_id == user_id)
            )
            prompt = result.scalar_one_or_none()
            
            if not prompt:
                return {
                    "prompt": OpenAIService.DEFAULT_SYSTEM_PROMPT,
                    "style_example": None
                }
            
            return {
                "prompt": prompt.system_prompt or OpenAIService.DEFAULT_SYSTEM_PROMPT,
                "style_example": prompt.style_example
            }
    
    @staticmethod
    async def update_prompt(user_id: int, prompt: str):
        async with async_session() as db:
            result = await db.execute(
                select(AIPrompt).where(AIPrompt.user_id == user_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.system_prompt = prompt
            else:
                new_prompt = AIPrompt(
                    user_id=user_id,
                    system_prompt=prompt
                )
                db.add(new_prompt)
            
            await db.commit()
            
            logger.info("prompt_updated", user_id=user_id)
    
    @staticmethod
    async def import_style(user_id: int, text: str):
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": OpenAIService.STYLE_ANALYSIS_PROMPT.format(text=text)}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            style_summary = response.choices[0].message.content.strip()
            
            async with async_session() as db:
                result = await db.execute(
                    select(AIPrompt).where(AIPrompt.user_id == user_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    existing.style_example = style_summary
                else:
                    new_prompt = AIPrompt(
                        user_id=user_id,
                        style_example=style_summary
                    )
                    db.add(new_prompt)
                
                await db.commit()
            
            logger.info("style_imported", user_id=user_id)
            
        except Exception as e:
            logger.error("style_import_error", user_id=user_id, error=str(e))
            raise
    
    @staticmethod
    async def analyze_project_for_match(project_description: str, user_skills: list) -> dict:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        prompt = f"""Analyze how well the user's skills match this project:

Project: {project_description}

User Skills: {', '.join(user_skills)}

Provide a match score (0-100) and brief explanation of why this is a good or bad fit."""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return {
                "analysis": response.choices[0].message.content.strip()
            }
        except Exception as e:
            logger.error("project_analysis_error", error=str(e))
            return {"analysis": "Unable to analyze project"}
