import sys
sys.path.insert(0, '/app')

import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from shared.database import async_session
from shared.models_db import User, NotificationSettings, Project, Filter, SeenProject
from sqlalchemy import select, and_
from app.config import settings
import structlog

logger = structlog.get_logger()

class NotificationService:
    API_URL = f"https://api.telegram.org/bot{settings.BOT_TOKEN}"
    
    @staticmethod
    async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = f"{NotificationService.API_URL}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        error = await response.text()
                        logger.error("telegram_send_error", chat_id=chat_id, error=error)
                        return False
            except Exception as e:
                logger.error("telegram_exception", chat_id=chat_id, error=str(e))
                return False
    
    @staticmethod
    async def check_and_send_notifications():
        logger.info("checking_immediate_notifications")
        
        async with async_session() as db:
            result = await db.execute(
                select(User, NotificationSettings)
                .join(NotificationSettings, NotificationSettings.user_id == User.id)
                .where(
                    and_(
                        NotificationSettings.enabled == True,
                        NotificationSettings.schedule == "immediate"
                    )
                )
            )
            users_with_settings = result.all()
            
            for user, notif_settings in users_with_settings:
                last_check = notif_settings.last_notification or datetime.utcnow() - timedelta(hours=1)
                
                new_projects = await NotificationService._get_filtered_projects_for_user(
                    db, user.id, last_check
                )
                
                if new_projects:
                    for project in new_projects[:5]:
                        message = NotificationService._format_project_message(project)
                        success = await NotificationService.send_telegram_message(
                            user.telegram_id, message
                        )
                        
                        if success:
                            seen = SeenProject(user_id=user.id, project_id=project["id"])
                            db.add(seen)
                    
                    notif_settings.last_notification = datetime.utcnow()
                    await db.commit()
    
    @staticmethod
    async def send_hourly_digests():
        logger.info("sending_hourly_digests")
        
        async with async_session() as db:
            result = await db.execute(
                select(User, NotificationSettings)
                .join(NotificationSettings, NotificationSettings.user_id == User.id)
                .where(
                    and_(
                        NotificationSettings.enabled == True,
                        NotificationSettings.schedule == "hourly"
                    )
                )
            )
            users_with_settings = result.all()
            
            for user, notif_settings in users_with_settings:
                last_check = notif_settings.last_notification or datetime.utcnow() - timedelta(hours=1)
                
                new_projects = await NotificationService._get_filtered_projects_for_user(
                    db, user.id, last_check
                )
                
                if new_projects:
                    message = NotificationService._format_digest_message(new_projects, "hourly")
                    success = await NotificationService.send_telegram_message(
                        user.telegram_id, message
                    )
                    
                    if success:
                        for project in new_projects:
                            seen = SeenProject(user_id=user.id, project_id=project["id"])
                            db.add(seen)
                        
                        notif_settings.last_notification = datetime.utcnow()
                        await db.commit()
    
    @staticmethod
    async def send_daily_digests():
        logger.info("sending_daily_digests")
        
        async with async_session() as db:
            result = await db.execute(
                select(User, NotificationSettings)
                .join(NotificationSettings, NotificationSettings.user_id == User.id)
                .where(
                    and_(
                        NotificationSettings.enabled == True,
                        NotificationSettings.schedule == "daily"
                    )
                )
            )
            users_with_settings = result.all()
            
            for user, notif_settings in users_with_settings:
                last_check = notif_settings.last_notification or datetime.utcnow() - timedelta(days=1)
                
                new_projects = await NotificationService._get_filtered_projects_for_user(
                    db, user.id, last_check
                )
                
                if new_projects:
                    message = NotificationService._format_digest_message(new_projects, "daily")
                    success = await NotificationService.send_telegram_message(
                        user.telegram_id, message
                    )
                    
                    if success:
                        for project in new_projects:
                            seen = SeenProject(user_id=user.id, project_id=project["id"])
                            db.add(seen)
                        
                        notif_settings.last_notification = datetime.utcnow()
                        await db.commit()
    
    @staticmethod
    async def _get_filtered_projects_for_user(db, user_id: int, since: datetime) -> List[Dict]:
        filter_result = await db.execute(
            select(Filter).where(Filter.user_id == user_id, Filter.is_active == True)
        )
        user_filter = filter_result.scalar_one_or_none()
        
        seen_subquery = select(SeenProject.project_id).where(SeenProject.user_id == user_id)
        
        query = select(Project).where(
            and_(
                Project.created_at > since,
                Project.id.not_in(seen_subquery)
            )
        ).order_by(Project.created_at.desc()).limit(20)
        
        if user_filter:
            import json
            from shared.utils import parse_list_field
            
            categories = parse_list_field(user_filter.categories)
            if categories:
                from sqlalchemy import or_
                category_conditions = [Project.category.ilike(f"%{cat}%") for cat in categories]
                query = query.where(or_(*category_conditions))
            
            keywords_include = parse_list_field(user_filter.keywords_include)
            if keywords_include:
                for kw in keywords_include:
                    query = query.where(
                        Project.title.ilike(f"%{kw}%") | Project.description.ilike(f"%{kw}%")
                    )
            
            if user_filter.budget_min:
                query = query.where(
                    (Project.budget_min >= user_filter.budget_min) | 
                    (Project.budget_max >= user_filter.budget_min)
                )
        
        result = await db.execute(query)
        projects = result.scalars().all()
        
        return [
            {
                "id": p.id,
                "external_id": p.external_id,
                "title": p.title,
                "description": p.description[:200],
                "budget_min": p.budget_min,
                "budget_max": p.budget_max,
                "url": p.url,
                "category": p.category
            }
            for p in projects
        ]
    
    @staticmethod
    def _format_project_message(project: Dict) -> str:
        budget_str = ""
        if project["budget_min"] and project["budget_max"]:
            budget_str = f"${project['budget_min']:.0f} - ${project['budget_max']:.0f}"
        elif project["budget_min"]:
            budget_str = f"From ${project['budget_min']:.0f}"
        elif project["budget_max"]:
            budget_str = f"Up to ${project['budget_max']:.0f}"
        
        return f"""🆕 Новый проект!

<b>{project['title']}</b>

{project['description']}

💰 Бюджет: {budget_str or 'Не указан'}
📁 Категория: {project['category'] or 'Не указана'}

👉 <a href="{project['url']}">Открыть проект</a>"""
    
    @staticmethod
    def _format_digest_message(projects: List[Dict], digest_type: str) -> str:
        count = len(projects)
        period = "час" if digest_type == "hourly" else "день"
        
        header = f"📬 Дайджест за {period}: {count} новых проектов\n\n"
        
        lines = []
        for i, p in enumerate(projects[:10], 1):
            budget = ""
            if p["budget_min"] and p["budget_max"]:
                budget = f" (${p['budget_min']:.0f}-${p['budget_max']:.0f})"
            elif p["budget_min"]:
                budget = f" (от ${p['budget_min']:.0f})"
            
            lines.append(f"{i}. <a href=\"{p['url']}\">{p['title']}</a>{budget}")
        
        footer = f"\n\n👉 /projects - посмотреть все проекты"
        
        return header + "\n".join(lines) + footer
    
    @staticmethod
    async def send_test_notification(telegram_id: int) -> bool:
        message = "✅ Уведомления работают! Вы будете получать новые проекты согласно настройкам."
        return await NotificationService.send_telegram_message(telegram_id, message)
