import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.page_context_service import PageElement, PageSnapshot
from automation.browser.dom_agent import DOMAgent

@pytest.mark.asyncio
async def test_execute_intent_deterministically_single_option_already_open():
    mock_page = MagicMock()
    agent = DOMAgent(mock_page)
    
    mock_handle = AsyncMock()
    agent.get_element_handle = AsyncMock(return_value=mock_handle)
    agent._click_element = AsyncMock()
    
    el_cms = PageElement(
        text="CMS (₹75,000.00)",
        role="option",
        tag="div",
        el_type="",
        name="",
        el_id="cms-opt",
        placeholder="",
        href=""
    )
    
    snapshot = PageSnapshot(
        url="https://crm.acesoftcloud.in/",
        title="CRM",
        elements=[el_cms]
    )
    
    with patch("automation.browser.browser_engine.BrowserEngine._animate_action", new_callable=AsyncMock):
        res = await agent.execute_intent_deterministically("select cms", snapshot)
        
        assert "Selected option" in res
        assert "cms" in res.lower()
        agent.get_element_handle.assert_called_once_with(el_cms)
        agent._click_element.assert_called_once_with(mock_handle)


@pytest.mark.asyncio
async def test_execute_intent_deterministically_single_option_closed_dropdown():
    mock_page = MagicMock()
    agent = DOMAgent(mock_page)
    
    mock_dropdown_handle = AsyncMock()
    mock_option_handle = AsyncMock()
    
    agent.get_element_handle = AsyncMock(side_effect=[mock_dropdown_handle, mock_option_handle])
    agent._click_element = AsyncMock()
    
    el_dropdown = PageElement(
        text="Select Product",
        role="combobox",
        tag="button",
        el_type="",
        name="Product",
        el_id="product-dropdown",
        placeholder="",
        href=""
    )
    
    initial_snapshot = PageSnapshot(
        url="https://crm.acesoftcloud.in/",
        title="CRM",
        elements=[el_dropdown]
    )
    
    el_cms = PageElement(
        text="CMS (₹75,000.00)",
        role="option",
        tag="div",
        el_type="",
        name="",
        el_id="cms-opt",
        placeholder="",
        href=""
    )
    fresh_snapshot = PageSnapshot(
        url="https://crm.acesoftcloud.in/",
        title="CRM",
        elements=[el_dropdown, el_cms]
    )
    
    from app.services.page_context_service import page_context_service
    original_get_snapshot = page_context_service.get_snapshot
    page_context_service.get_snapshot = AsyncMock(return_value=fresh_snapshot)
    
    try:
        with patch("automation.browser.browser_engine.BrowserEngine._animate_action", new_callable=AsyncMock):
            res = await agent.execute_intent_deterministically("select cms", initial_snapshot)
            
            assert "Opened dropdown and selected option" in res
            assert agent._click_element.call_count == 2
    finally:
        page_context_service.get_snapshot = original_get_snapshot


@pytest.mark.asyncio
async def test_execute_intent_deterministically_preserve_casing():
    mock_page = MagicMock()
    agent = DOMAgent(mock_page)
    
    mock_handle = AsyncMock()
    agent.get_element_handle = MagicMock(return_value=mock_handle)
    agent._click_element = AsyncMock()
    agent._fill_input = AsyncMock(return_value="Reset@123")
    
    el_password = PageElement(
        text="Password",
        role="textbox",
        tag="input",
        el_type="password",
        name="password",
        el_id="password-input",
        placeholder="Enter your password",
        href=""
    )
    
    snapshot = PageSnapshot(
        url="https://crm.acesoftcloud.in/",
        title="CRM",
        elements=[el_password]
    )
    
    with patch("automation.browser.browser_engine.BrowserEngine._animate_action", new_callable=AsyncMock):
        # Test 1: Implicit pattern ("password Reset@123")
        res = await agent.execute_intent_deterministically("password Reset@123", snapshot)
        assert "Reset@123" in res
        agent._fill_input.assert_called_with(mock_handle, el_password, "Reset@123")
        
        # Test 2: Explicit pattern ("set password to Reset@123")
        res_explicit = await agent.execute_intent_deterministically("set password to Reset@123", snapshot)
        assert "Reset@123" in res_explicit

