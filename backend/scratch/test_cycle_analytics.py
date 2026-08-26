import os
import sys
import time
import json

# Ensure the parent directory is in path
MODEL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(MODEL_DIR)

import bms_dashboard_backend

# Set temporary test history path
TEST_HISTORY_PATH = os.path.join(MODEL_DIR, "scratch", "test_cycle_history.json")
bms_dashboard_backend.CYCLE_HISTORY_PATH = TEST_HISTORY_PATH

def clean_test_history():
    if os.path.exists(TEST_HISTORY_PATH):
        try:
            os.remove(TEST_HISTORY_PATH)
        except Exception:
            pass

def save_mock_history(history):
    with open(TEST_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)

def generate_mock_cycle(cycle_id, ctype, status="Full", est_ah=5.0, est_wh=160.0, avg_curr=10.0, duration=1800, temp_rise=5.0, spread_start=0.01, spread_end=0.02):
    return {
        "cycle_id": cycle_id,
        "type": ctype,
        "start_time": "2026-06-19 20:00:00",
        "end_time": "2026-06-19 20:30:00",
        "duration_sec": duration,
        "start_soc": 20.0 if ctype == "Charge" else 80.0,
        "end_soc": 96.0 if ctype == "Charge" else 35.0,
        "soc_change": 76.0 if ctype == "Charge" else -45.0,
        "start_voltage": 24.2,
        "end_voltage": 32.8,
        "max_cell_voltage": 4.1,
        "min_cell_voltage": 2.9,
        "voltage_spread_start": spread_start,
        "voltage_spread_end": spread_end,
        "avg_current": avg_curr,
        "peak_current": avg_curr * 1.2,
        "max_temp": 30.0 + temp_rise,
        "temp_rise": temp_rise,
        "est_ah": est_ah,
        "est_wh": est_wh,
        "status": status,
        "partial_reason": "N/A",
        "alerts_count": 0,
        "data_quality_score": 1.0
    }

def run_tests():
    print("==================================================")
    print("BMS CYCLE HEALTH ANALYTICS INTEGRATION TEST SUITE")
    print("==================================================")
    
    # --------------------------------------------------
    # Scenario 1: Insufficient cycle history
    # --------------------------------------------------
    print("\nScenario 1: Testing Insufficient Cycle History (< 3 cycles)")
    clean_test_history()
    save_mock_history([])
    
    # Active charge cycle
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 1,
        "type": "Charge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 300,
        "start_soc": 20.0,
        "start_voltage": 24.2,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 25.0, "current": 10.0, "voltage": 25.0, "temperature": 26.0}],
        "ah_accumulated": 0.83,
        "wh_accumulated": 20.8,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["confidence_score"] == "Low", f"Expected Low confidence, got {summary['confidence_score']}"
    assert "insufficient" in summary["degradation_trend"], "Expected insufficient history warning"
    print("Scenario 1 PASSED: Correctly flagged low confidence / insufficient history.")

    # --------------------------------------------------
    # Scenario 2: Normal full charge cycle
    # --------------------------------------------------
    print("\nScenario 2: Testing Normal Full Charge Cycle (High Confidence)")
    history = [generate_mock_cycle(i, "Charge") for i in range(1, 6)]
    save_mock_history(history)
    
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 6,
        "type": "Charge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 600,  # 10 mins elapsed
        "start_soc": 20.0,
        "start_voltage": 24.2,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 45.4, "current": 10.0, "voltage": 28.0, "temperature": 27.0}],
        "ah_accumulated": 1.67,
        "wh_accumulated": 46.7,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["confidence_score"] == "High", f"Expected High confidence, got {summary['confidence_score']}"
    assert summary["degradation_trend"] == "No degradation trend", f"Expected normal health, got {summary['degradation_trend']}"
    assert summary["partial_status"] == "Normal", f"Expected Normal status, got {summary['partial_status']}"
    print("Scenario 2 PASSED: Healthy charge cycle diagnosed correctly.")

    # --------------------------------------------------
    # Scenario 3: Normal full discharge cycle
    # --------------------------------------------------
    print("\nScenario 3: Testing Normal Full Discharge Cycle")
    history = [generate_mock_cycle(i, "Discharge") for i in range(1, 6)]
    save_mock_history(history)
    
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 6,
        "type": "Discharge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 600,
        "start_soc": 80.0,
        "start_voltage": 32.8,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 65.0, "current": -10.0, "voltage": 28.0, "temperature": 27.0}],
        "ah_accumulated": 1.67,
        "wh_accumulated": 46.7,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["confidence_score"] == "High", f"Expected High confidence, got {summary['confidence_score']}"
    assert summary["degradation_trend"] == "No degradation trend", f"Expected normal health, got {summary['degradation_trend']}"
    print("Scenario 3 PASSED: Healthy discharge cycle diagnosed correctly.")

    # --------------------------------------------------
    # Scenario 4: Partial charge suspected
    # --------------------------------------------------
    print("\nScenario 4: Testing Partial Charge Suspected (low current in middle SOC)")
    history = [generate_mock_cycle(i, "Charge") for i in range(1, 6)]
    save_mock_history(history)
    
    # Charging current dropped to < 0.2A at SOC 70%
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 6,
        "type": "Charge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 600,
        "start_soc": 20.0,
        "start_voltage": 24.2,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 70.0, "current": 0.1, "voltage": 28.0, "temperature": 27.0}],
        "ah_accumulated": 1.67,
        "wh_accumulated": 46.7,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["partial_status"] == "Partial Charge Suspected", f"Expected Partial Charge Suspected, got {summary['partial_status']}"
    print("Scenario 4 PASSED: Early charge cut/partial charging detected successfully.")

    # --------------------------------------------------
    # Scenario 5: Partial discharge suspected
    # --------------------------------------------------
    print("\nScenario 5: Testing Partial Discharge Suspected (low load in middle SOC)")
    history = [generate_mock_cycle(i, "Discharge") for i in range(1, 6)]
    save_mock_history(history)
    
    # Discharging current dropped to < 0.05A at SOC 55%
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 6,
        "type": "Discharge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 600,
        "start_soc": 80.0,
        "start_voltage": 32.8,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 55.0, "current": -0.01, "voltage": 28.0, "temperature": 27.0}],
        "ah_accumulated": 1.67,
        "wh_accumulated": 46.7,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["partial_status"] == "Partial Discharge Suspected", f"Expected Partial Discharge Suspected, got {summary['partial_status']}"
    print("Scenario 5 PASSED: Early discharge cut/partial discharging detected successfully.")

    # --------------------------------------------------
    # Scenario 6: Degraded charging (capacity degradation)
    # --------------------------------------------------
    print("\nScenario 6: Testing Degraded Charging (Usable capacity drop > 6%)")
    # Baseline with avg est_ah = 10.0 Ah
    history = [generate_mock_cycle(i, "Charge", est_ah=10.0) for i in range(1, 6)]
    save_mock_history(history)
    
    # Active cycle: ah = 0.54, but SOC moved by 6.0% (meaning capacity = 0.54 / 0.06 = 9.0 Ah, which is 10% drop)
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 6,
        "type": "Charge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 600,
        "start_soc": 20.0,
        "start_voltage": 24.2,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 26.0, "current": 10.0, "voltage": 28.0, "temperature": 27.0}],
        "ah_accumulated": 0.54,
        "wh_accumulated": 15.0,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert "degradation" in summary["degradation_trend"], f"Expected degradation trend warning, got: {summary['degradation_trend']}"
    assert "capacity is 10% lower" in summary["comparison_insight"], f"Expected capacity message in insight, got: {summary['comparison_insight']}"
    print("Scenario 6 PASSED: Slower charging capacity degradation detected successfully.")

    # --------------------------------------------------
    # Scenario 7: Degraded discharging (faster SOC drop / runtime drop)
    # --------------------------------------------------
    print("\nScenario 7: Testing Degraded Discharging (Runtime drop > 15% across cycles)")
    # Baseline: First discharge is 2000s, last discharge is 1650s (not degraded enough), or let's make it 1600s (< 1700s)
    history = [
        generate_mock_cycle(1, "Discharge", duration=2000),
        generate_mock_cycle(2, "Discharge", duration=1950),
        generate_mock_cycle(3, "Discharge", duration=1800),
        generate_mock_cycle(4, "Discharge", duration=1700),
        generate_mock_cycle(5, "Discharge", duration=1600), # 1600 < 2000 * 0.85 = 1700
    ]
    save_mock_history(history)
    
    # Active cycle: Idle (degradation trend check pulls the last 5 discharges)
    bms_dashboard_backend.active_cycle = {
        "cycle_id": None,
        "type": None,
        "start_time": None,
        "start_time_epoch": None,
        "start_soc": None,
        "start_voltage": None,
        "voltage_spread_start": None,
        "rows": [],
        "ah_accumulated": 0.0,
        "wh_accumulated": 0.0,
        "last_timestamp_epoch": None,
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert "degradation" in summary["degradation_trend"], f"Expected degradation trend warning, got: {summary['degradation_trend']}"
    print("Scenario 7 PASSED: Faster discharging runtime drop trend detected successfully.")

    # --------------------------------------------------
    # Scenario 8: Increasing cell voltage spread
    # --------------------------------------------------
    print("\nScenario 8: Testing Increasing Cell Voltage Spread")
    # Baseline: First spread 0.02, last spread 0.05 (> 0.02 * 1.2 = 0.024)
    history = [
        generate_mock_cycle(1, "Discharge", spread_end=0.02),
        generate_mock_cycle(2, "Discharge", spread_end=0.025),
        generate_mock_cycle(3, "Discharge", spread_end=0.03),
        generate_mock_cycle(4, "Discharge", spread_end=0.04),
        generate_mock_cycle(5, "Discharge", spread_end=0.05),
    ]
    save_mock_history(history)
    
    bms_dashboard_backend.active_cycle = {
        "cycle_id": None,
        "type": None,
        "start_time": None,
        "start_time_epoch": None,
        "start_soc": None,
        "start_voltage": None,
        "voltage_spread_start": None,
        "rows": [],
        "ah_accumulated": 0.0,
        "wh_accumulated": 0.0,
        "last_timestamp_epoch": None,
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["cell_imbalance_trend"] == "Cell imbalance trend increasing", f"Expected cell imbalance trend warning, got: {summary['cell_imbalance_trend']}"
    assert "degradation" in summary["degradation_trend"], f"Expected degradation trend warning, got: {summary['degradation_trend']}"
    print("Scenario 8 PASSED: Rising cell voltage imbalance trend detected successfully.")

    # --------------------------------------------------
    # Scenario 9: Increasing temperature rise
    # --------------------------------------------------
    print("\nScenario 9: Testing Increasing Temperature Rise")
    # Baseline: First temp_rise 5.0, last 7.0 (> 5.0 * 1.2 = 6.0)
    history = [
        generate_mock_cycle(1, "Discharge", temp_rise=5.0),
        generate_mock_cycle(2, "Discharge", temp_rise=5.5),
        generate_mock_cycle(3, "Discharge", temp_rise=6.0),
        generate_mock_cycle(4, "Discharge", temp_rise=6.5),
        generate_mock_cycle(5, "Discharge", temp_rise=7.0),
    ]
    save_mock_history(history)
    
    bms_dashboard_backend.active_cycle = {
        "cycle_id": None,
        "type": None,
        "start_time": None,
        "start_time_epoch": None,
        "start_soc": None,
        "start_voltage": None,
        "voltage_spread_start": None,
        "rows": [],
        "ah_accumulated": 0.0,
        "wh_accumulated": 0.0,
        "last_timestamp_epoch": None,
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["thermal_rise_trend"] == "Thermal rise increasing", f"Expected thermal rise trend warning, got: {summary['thermal_rise_trend']}"
    assert "degradation" in summary["degradation_trend"], f"Expected degradation trend warning, got: {summary['degradation_trend']}"
    print("Scenario 9 PASSED: Rising thermal load profile detected successfully.")

    # --------------------------------------------------
    # Scenario 10: Load difference (reducing confidence score)
    # --------------------------------------------------
    print("\nScenario 10: Testing Load Difference (Medium Confidence)")
    # Baseline: Charging current is 10.0 A
    history = [generate_mock_cycle(i, "Charge", avg_curr=10.0) for i in range(1, 6)]
    save_mock_history(history)
    
    # Active cycle: Charging current is 14.0 A (difference 4.0 A > 3.0 A)
    bms_dashboard_backend.active_cycle = {
        "cycle_id": 6,
        "type": "Charge",
        "start_time": "2026-06-19 21:00:00",
        "start_time_epoch": time.time() - 3600,  # 1 hour ago
        "start_soc": 20.0,
        "start_voltage": 24.2,
        "voltage_spread_start": 0.01,
        "rows": [{"soc": 50.0, "current": 14.0, "voltage": 28.0, "temperature": 27.0}],
        "ah_accumulated": 14.0,  # 14.0 Ah in 1 hour = 14.0 A average
        "wh_accumulated": 392.0,
        "last_timestamp_epoch": time.time(),
        "consecutive_idle": 0,
        "consecutive_opposite": 0
    }
    
    summary = bms_dashboard_backend.get_cycle_analytics_summary()
    assert summary["confidence_score"] == "Medium", f"Expected Medium confidence, got {summary['confidence_score']}"
    assert "load condition is different" in summary["confidence_reason"], f"Expected load difference reason, got: {summary['confidence_reason']}"
    print("Scenario 10 PASSED: Confidence downgraded correctly due to high load difference.")

    print("\n==================================================")
    print("ALL 10 SCENARIOS PASSED SUCCESSFULLY!")
    print("==================================================")
    clean_test_history()

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\nTEST FAILURE: {e}")
        clean_test_history()
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        clean_test_history()
        sys.exit(1)
