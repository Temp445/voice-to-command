import pytest
from app.services.command_service import CommandService, Intent

@pytest.fixture
def command_service(monkeypatch):
    from automation.browser.browser_engine import BrowserEngine
    monkeypatch.setattr(BrowserEngine, "get_active_page", lambda self: None)
    
    service = CommandService()
    # Register a few simple intents for testing
    
    async def mock_handler(app: str = "", **kwargs):
        return f"Opening {app}"
        
    async def mock_search(query: str = "", **kwargs):
        return f"Searching for {query}"
        
    service.register(Intent(
        name="open_app",
        description="Open an application",
        patterns=[r"(?:open|launch|start) (?P<app>[\w\s]+)"],
        param_names=["app"],
        handler=mock_handler
    ))
    
    service.register(Intent(
        name="search_google",
        description="Search Google",
        patterns=[r"(?:search|google|lookup) (?P<query>[\w\s]+)"],
        param_names=["query"],
        handler=mock_search
    ))
    
    return service

@pytest.mark.asyncio
async def test_intent_fast_path_exact_match(command_service):
    """Test that regex patterns correctly match and extract parameters."""
    result = await command_service.parse_and_execute("open notepad")
    # Result should be the dict returned by the command service
    assert result["result"] == "Opening notepad"
    
    result2 = await command_service.parse_and_execute("search Python programming")
    assert result2["result"] == "Searching for Python programming"

@pytest.mark.asyncio
async def test_intent_no_match(command_service):
    """Test behavior when no fast-path regex matches and LLM is disabled."""
    # Since we didn't mock LLMService here, but LLMService is default disabled
    # parse_and_execute should return an error or fallback string.
    result = await command_service.parse_and_execute("do something unknown")
    
    # In command_service.py, if no match and LLM is disabled, it returns:
    # "I didn't understand that command." or a friendly fallback.
    res_lower = result["result"].lower()
    assert "didn't understand" in res_lower or "not sure what you mean" in res_lower

def test_intent_registry_registration(command_service):
    """Test that intents are correctly registered in the service."""
    assert len(command_service._intents) == 2
    assert command_service._intents[0].name == "open_app"
    assert command_service._intents[1].name == "search_google"
    assert command_service._intents[0].param_names == ["app"]

def test_real_click_text_intent():
    """Test that the real click_text intent regex patterns match edit and view commands."""
    from app.services.command_service import command_service
    from app.services.intent_registry import register_all_intents
    
    # Backup existing intents and clear
    old_intents = list(command_service._intents)
    command_service._intents = []
    
    try:
        register_all_intents()
        click_text_intent = next((i for i in command_service._intents if i.name == "click_text"), None)
        assert click_text_intent is not None
        
        # Test edit matching
        matched, params = click_text_intent.match("edit the 6 months installments request")
        assert matched
        assert params["action"] == "edit"
        assert params["text"] == "6 months installments request"
        
        # Test view matching
        matched, params = click_text_intent.match("view the employee Nivin S request")
        assert matched
        assert params["action"] == "view"
        assert params["text"] == "employee Nivin S request"
    finally:
        # Restore intents
        command_service._intents = old_intents


def test_find_best_element_context_and_penalties():
    from app.services.page_context_service import PageElement, find_best_element

    # Scenario: User wants to "view the 6 months installments request"
    query = "view the 6 months installments request"

    # Element 1: "View" button in a notification (should be penalized/ignored)
    el_notif = PageElement(
        text="View",
        role="button",
        tag="button",
        el_type="",
        name="",
        el_id="",
        placeholder="",
        href="",
        context="Notification: 6 months installments request approved",
        is_nav_header_or_notification=True,
    )

    # Element 2: "View" button in the actual table row (should match)
    el_row = PageElement(
        text="View",
        role="button",
        tag="button",
        el_type="",
        name="",
        el_id="",
        placeholder="",
        href="",
        context="Pending request 6 months installments for employee Nivin S",
        is_nav_header_or_notification=False,
    )

    # Element 3: A generic unrelated "View" button
    el_unrelated = PageElement(
        text="View",
        role="button",
        tag="button",
        el_type="",
        name="",
        el_id="",
        placeholder="",
        href="",
        context="Some other random table row text",
        is_nav_header_or_notification=False,
    )

    # Element 4: Notification bell button in header
    el_bell = PageElement(
        text="Notifications",
        role="button",
        tag="button",
        el_type="",
        name="View notifications",
        el_id="",
        placeholder="",
        href="",
        context="",
        is_nav_header_or_notification=True,
    )

    elements = [el_notif, el_row, el_unrelated, el_bell]

    # Matching with roles=("button",)
    matched = find_best_element(elements, query, min_score=45, roles=("button",))
    assert matched is el_row

    # Scenario 2: User explicitly wants to "view notifications"
    query_notif = "view notifications"
    # The notification element should be matched since query explicitly mentions it
    matched_notif = find_best_element(elements, query_notif, min_score=40, roles=("button",))
    assert matched_notif is el_bell


def test_real_set_field_intent():
    """Test that the set_field intent correctly matches set and fill commands and extracts parameters."""
    from app.services.command_service import command_service
    from app.services.intent_registry import register_all_intents
    
    # Backup existing intents and clear
    old_intents = list(command_service._intents)
    command_service._intents = []
    
    try:
        register_all_intents()
        set_field_intent = next((i for i in command_service._intents if i.name == "set_field"), None)
        assert set_field_intent is not None
        
        # Test explicit set command
        matched, params = set_field_intent.match("set deduction start month to june")
        assert matched
        assert params["text"] == "set deduction start month to june"
        
        # Test implicit set command
        matched, params = set_field_intent.match("deduction start month jun")
        assert matched
        assert params["text"] == "deduction start month jun"
        
        # Test implicit numeric set command
        matched, params = set_field_intent.match("interest rate 0")
        assert matched
        assert params["text"] == "interest rate 0"
    finally:
        # Restore intents
        command_service._intents = old_intents



