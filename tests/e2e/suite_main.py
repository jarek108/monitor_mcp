import asyncio
import os
import sys
from playwright.async_api import async_playwright
from pathlib import Path

async def run_test(run_dir):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("Navigating to Streamlit...")
            await page.goto("http://localhost:8501")
            await page.wait_for_selector("section[data-testid='stSidebar']", timeout=20000)
            await asyncio.sleep(2) # Stabilization
            
            # --- Test A: Layout State - Idle/Monitoring ---
            print("--- Test A: Unified Layout (Idle state) ---")
            
            # Assert Top section exists
            live_stream_header = page.get_by_role("heading", name="Live Stream")
            assert await live_stream_header.is_visible(), "SPEC VIOLATION: Live Stream section missing."
            
            # Assert Dynamic Bottom Section is in History Mode
            history_header = page.get_by_role("heading", name="Recent History")
            assert await history_header.is_visible(), "SPEC VIOLATION: Recent History should be visible when idle."
            
            ai_logs_header = page.get_by_role("heading", name="AI Analysis Logs")
            assert not await ai_logs_header.is_visible(), "SPEC VIOLATION: AI Analysis Logs should be hidden when idle."
            print("[PASS] Unified Layout (Idle)")

            # --- Test B: AI Simulation (Autonomous Stop & Sync) ---
            print("--- Test B: Autonomous Simulation Lifecycle & Layout Swap ---")
            ai_sandbox_expander = page.locator("div[data-testid='stExpander']").filter(has_text="AI Sandbox")
            
            if await ai_sandbox_expander.is_visible():
                folder_input = ai_sandbox_expander.get_by_label("Folder")
                if not await folder_input.is_visible():
                    print("Expanding AI Sandbox...")
                    await ai_sandbox_expander.locator("summary").click()
                    await asyncio.sleep(2)
                
                if await folder_input.is_visible():
                    mock_path = str(Path("tests/e2e/mock_recording").absolute())
                    await folder_input.fill(mock_path)
                    print(f"Filled Folder with mock path: {mock_path}")
                    
                    start_sim_button = ai_sandbox_expander.get_by_role("button", name="Start Sim", exact=True)
                    stop_sim_button = ai_sandbox_expander.get_by_role("button", name="Stop Sim", exact=True)
                    
                    await start_sim_button.click()
                    print("Clicked Start Sim. Asserting immediate UI state...")
                    await asyncio.sleep(2)
                    
                    # Layout Swap Assertion
                    assert await ai_logs_header.is_visible(), "SPEC VIOLATION: AI Analysis Logs should appear when Simulation starts."
                    assert not await history_header.is_visible(), "SPEC VIOLATION: Recent History should be hidden when Simulation starts."
                    print("[PASS] Unified Layout (Simulation Mode)")

                    # Auto-Selection Assertion
                    session_radio_group = page.get_by_role("radiogroup", name="Select Session")
                    checked_radio = session_radio_group.locator("input[type='radio']:checked")
                    assert await checked_radio.count() == 1, "SPEC VIOLATION: No session or multiple sessions auto-selected."
                    selected_value = await checked_radio.get_attribute("value")
                    print(f"Auto-selected session: {selected_value}")
                    print("[PASS] Persistent Session Navigation (Auto-Selection)")
                    
                    # ASSERTION: Immediate state sync (Spec 2.2)
                    assert await start_sim_button.is_disabled(), "SPEC VIOLATION: Start Sim button did not disable!"
                    assert await stop_sim_button.is_enabled(), "SPEC VIOLATION: Stop Sim button did not enable!"
                    print("[PASS] UI State Synchronization (Start)")
                    
                    print("Waiting for autonomous termination (FolderFeeder exhaust)...")
                    success = False
                    for i in range(30):
                        await asyncio.sleep(1)
                        try:
                            expander = page.locator("div[data-testid='stExpander']").filter(has_text="AI Sandbox")
                            folder_visible = await expander.get_by_label("Folder").is_visible()
                            
                            if not folder_visible:
                                print("AI Sandbox expander collapsed. Simulation state reset successfully.")
                                success = True
                                break
                                
                            current_start = expander.get_by_role("button", name="Start Sim", exact=True)
                            current_stop = expander.get_by_role("button", name="Stop Sim", exact=True)
                            
                            if await current_start.is_visible() and await current_stop.is_visible():
                                if await current_start.is_enabled() and await current_stop.is_disabled():
                                    print("Buttons reset to default state successfully.")
                                    success = True
                                    break
                        except Exception:
                            continue
                    
                    if not success:
                        screenshot_path_sim = os.path.join(run_dir, "sim_autonomous_failure.png")
                        await page.screenshot(path=screenshot_path_sim)
                        print(f"Captured failure screenshot: {screenshot_path_sim}")
                        
                    assert success, "SPEC VIOLATION: UI did not automatically reset after simulation completion!"
                    print("[PASS] UI State Synchronization (Autonomous Stop)")
                    
                    # --- Test C: Retrospective Viewing Contract ---
                    print("--- Test C: Retrospective Viewing (Offline State) ---")
                    await page.reload()
                    await page.wait_for_selector("section[data-testid='stSidebar']", timeout=20000)
                    await asyncio.sleep(2)
                    
                    assert await ai_logs_header.is_visible(), "SPEC VIOLATION: AI Analysis Logs should automatically render on reload if latest session is a sim."
                    print("[PASS] Retrospective Auto-Selection on Reload")
                    
                    radio_label = page.locator("label").filter(has_text=selected_value)
                    if await radio_label.count() > 0:
                        await radio_label.first.click()
                        print(f"Clicked historical session: {selected_value}")
                        await asyncio.sleep(1)
                        
                        assert await ai_logs_header.is_visible(), "SPEC VIOLATION: AI Analysis Logs did NOT appear when clicking historical session!"
                        assert not await history_header.is_visible(), "SPEC VIOLATION: Recent History remained visible incorrectly."
                        print("[PASS] Retrospective Viewing Contract")
                    else:
                        print("Could not find the historical session in the radio list to click.")

                    # --- Test D: UI State Persistence ---
                    print("--- Test D: UI State Persistence (Spec 5.1) ---")
                    # Re-expand AI Sandbox
                    expander = page.locator("div[data-testid='stExpander']").filter(has_text="AI Sandbox")
                    if not await expander.get_by_label("Model").is_visible():
                        print("Expanding AI Sandbox for persistence test...")
                        await expander.locator("summary").click()
                        await asyncio.sleep(1)
                    
                    # Change a setting: Simulation Model
                    target_model = "gemini-2.0-flash-lite-preview-02-05"
                    # In Streamlit, selectboxes are often comboboxes. We click and then select.
                    model_selector = expander.get_by_label("Model")
                    # Try direct selection first, but Streamlit is tricky
                    await model_selector.click()
                    await page.get_by_text(target_model, exact=True).click()
                    
                    print(f"Changed Model to: {target_model}")
                    await asyncio.sleep(2) # Wait for on_change=save_ui_state to fire
                    
                    # Reload page (cold start)
                    await page.reload()
                    await page.wait_for_selector("section[data-testid='stSidebar']", timeout=20000)
                    await asyncio.sleep(2)
                    
                    # Re-expand
                    expander = page.locator("div[data-testid='stExpander']").filter(has_text="AI Sandbox")
                    if not await expander.get_by_label("Model").is_visible():
                        await expander.locator("summary").click()
                        await asyncio.sleep(1)
                    
                    # ASSERTION: Model value was preserved
                    # For Streamlit, the label of the selected option is usually shown in the aria-label or a specific div
                    # The input itself might have the value.
                    restored_model_input = expander.get_by_label("Model")
                    restored_model = await restored_model_input.input_value()
                    # Wait, for st.selectbox, the value attribute of the hidden input is usually the label or index
                    # But get_by_label might point to the visible element which has the text.
                    # Let's check the text of the container if input_value is empty.
                    if not restored_model:
                        # Fallback: check the text content of the element or its parent
                        restored_model = await expander.locator("div[data-testid='stSelectbox']").inner_text()
                        # Inner text will contain the selected option
                    
                    print(f"Restored Model value: {restored_model}")
                    assert target_model in restored_model, f"SPEC VIOLATION: Model setting not persisted! Expected {target_model} to be in {restored_model}"
                    print("[PASS] UI State Persistence (Model Setting)")

                else:
                    print("Folder input not visible.")
            else:
                print("AI Sandbox expander not found.")
                
        except AssertionError as e:
            print(f"ASSERTION FAILED: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Test run error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            await browser.close()
            print("Browser closed.")

if __name__ == "__main__":
    run_directory = sys.argv[1] if len(sys.argv) > 1 else "."
    asyncio.run(run_test(run_directory))
