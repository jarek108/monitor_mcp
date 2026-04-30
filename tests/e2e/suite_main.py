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
                    # The radio list is identified by "Select Session"
                    session_radio_group = page.get_by_role("radiogroup", name="Select Session")
                    # We expect the newest session to be checked
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
                        except Exception:
                            continue
                    
                    if not success:
                        screenshot_path_sim = os.path.join(run_dir, "sim_autonomous_failure.png")
                        await page.screenshot(path=screenshot_path_sim)
                        print(f"Captured failure screenshot: {screenshot_path_sim}")
                        
                    # ASSERTION: Autonomous State Reset (Spec 2.2/2.3)
                    assert success, "SPEC VIOLATION: UI did not automatically reset after simulation completion!"
                    print("[PASS] UI State Synchronization (Autonomous Stop)")
                    
                    # --- Test C: Retrospective Viewing Contract ---
                    print("--- Test C: Retrospective Viewing (Offline State) ---")
                    # Reload the page to simulate a cold start
                    await page.reload()
                    await page.wait_for_selector("section[data-testid='stSidebar']", timeout=20000)
                    await asyncio.sleep(2)
                    
                    # Because we just ran a simulation, auto-selection should immediately select it
                    # on cold start, so AI Analysis Logs should be visible without us even clicking.
                    assert await ai_logs_header.is_visible(), "SPEC VIOLATION: AI Analysis Logs should automatically render on reload if latest session is a sim."
                    print("[PASS] Retrospective Auto-Selection on Reload")
                    
                    # Let's explicitly click it anyway to fulfill the contract test mechanics
                    radio_label = page.locator("label").filter(has_text=selected_value)
                    if await radio_label.count() > 0:
                        await radio_label.first.click()
                        print(f"Clicked historical session: {selected_value}")
                        await asyncio.sleep(1)
                        
                        # Layout Swap Assertion (Retrospective)
                        assert await ai_logs_header.is_visible(), "SPEC VIOLATION: AI Analysis Logs did NOT appear when clicking historical session!"
                        assert not await history_header.is_visible(), "SPEC VIOLATION: Recent History remained visible incorrectly."
                        print("[PASS] Retrospective Viewing Contract")
                        
                        screenshot_path_retro = os.path.join(run_dir, "sim_retrospective_success.png")
                        await page.screenshot(path=screenshot_path_retro)
                    else:
                        print("Could not find the historical session in the radio list to click.")

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