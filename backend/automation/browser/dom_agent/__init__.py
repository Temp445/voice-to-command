from playwright.async_api import Page
from .element_finder import ElementFinderMixin
from .action_executor import ActionExecutorMixin
from .state_manager import StateManagerMixin

class DOMAgent(ElementFinderMixin, ActionExecutorMixin, StateManagerMixin):
    def __init__(self, page: Page):
        self.page = page
        StateManagerMixin.__init__(self)
