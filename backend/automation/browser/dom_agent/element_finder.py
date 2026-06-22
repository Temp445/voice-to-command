from loguru import logger
from playwright.async_api import Page
from app.services.llm.llm_service import llm_service
from app.config import settings

class ElementFinderMixin:
