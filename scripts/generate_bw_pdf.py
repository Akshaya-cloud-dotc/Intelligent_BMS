import os
import subprocess
import shutil
import pypdf

html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>AI-PBMS Technical Project Report</title>
<style>
  @page {
    size: A4 portrait;
    margin: 11mm 15mm 10mm 15mm;
  }
  * {
    box-sizing: border-box;
  }
  body {
    font-family: 'Times New Roman', Times, serif;
    color: #000000;
    line-height: 1.28;
    font-size: 8.8pt;
    margin: 0;
    padding: 0;
    background: #ffffff;
  }
  .page {
    page-break-after: always;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .page:last-child {
    page-break-after: avoid;
  }
  
  /* Traditional Academic / Engineering Report Header */
  .doc-header {
    text-align: center;
    border-bottom: 1.2pt solid #000000;
    padding-bottom: 5px;
    margin-bottom: 7px;
  }
  .doc-title {
    font-size: 13.5pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.2px;
    margin-bottom: 2px;
  }
  .doc-subtitle {
    font-size: 9.5pt;
    font-style: italic;
    margin-bottom: 3px;
  }
  .doc-meta {
    font-size: 8.5pt;
  }

  .sec-heading {
    font-size: 9.3pt;
    font-weight: bold;
    text-transform: uppercase;
    margin: 6px 0 2px 0;
    border-bottom: 0.5pt solid #000000;
    padding-bottom: 1px;
    letter-spacing: 0.2px;
  }

  p {
    margin: 2px 0 4px 0;
    text-align: justify;
  }

  ul {
    margin: 1.5px 0 4px 0;
    padding-left: 17px;
  }

  li {
    margin-bottom: 1.5px;
    text-align: justify;
  }

  /* Academic Booktabs Table Style */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 8.0pt;
    margin: 4px 0;
    line-height: 1.22;
  }
  th {
    border-top: 1.2pt solid #000000;
    border-bottom: 0.8pt solid #000000;
    padding: 3px 4px;
    text-align: left;
    font-weight: bold;
  }
  td {
    border-bottom: 0.4pt solid #d1d5db;
    padding: 2.8px 4px;
    vertical-align: top;
  }
  tr:last-child td {
    border-bottom: 1.2pt solid #000000;
  }

  .footer-text {
    border-top: 0.5pt solid #000000;
    padding-top: 3px;
    font-size: 7.5pt;
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
  }
</style>
</head>
<body>

<!-- ==================== PAGE 1 ==================== -->
<div class="page">
  <div>
    <div class="doc-header">
      <div class="doc-title">Design and Implementation of an Intelligent Battery Management System (AI-PBMS)</div>
      <div class="doc-subtitle">A Physics-Informed Machine Learning Framework for Real-Time EV Battery Fault Diagnosis</div>
      <div class="doc-meta">Team ANS_4X &middot; PSG Institute of Technology and Applied Research (PSG iTech)</div>
    </div>

    <div class="sec-heading">1. Project Overview & Problem Statement</div>
    <ul>
      <li><strong>Context:</strong> Lithium-ion battery packs deployed in electric vehicles (EVs) and energy storage systems (ESS) are prone to accelerated degradation and catastrophic thermal runaway caused by internal short circuits, cell divergence, sensor disconnects, and overcurrent abuse.</li>
      <li><strong>Existing Limitations:</strong> Conventional commercial BMS rely purely on static, hard-coded threshold limits. They fail to identify latent internal faults (such as early-stage micro-shorts or weak cell impedance growth) before severe voltage collapse or thermal escalation occurs. Conversely, pure black-box deep learning models suffer from false alarms and unpredictable outputs when operating out-of-distribution.</li>
      <li><strong>Project Objective:</strong> We developed an edge-deployable, dual-layer Battery Management System combining real-time deterministic electrochemical physics boundaries with a supervised XGBoost machine learning engine to achieve reliable, sub-second early fault detection with zero critical false negatives.</li>
    </ul>

    <div class="sec-heading">2. Battery Pack Specifications & Hardware Interfacing</div>
    <ul>
      <li><strong>Pack Architecture:</strong> 8S2P configuration constructed using LG Energy Solution INR21700-M50 cylindrical Li-ion cells (NMC-811 chemistry, 3.63 V nominal, 5000 mAh per cell).</li>
      <li><strong>Operating Parameters:</strong> Nominal voltage: 29.04 V; Fully charged cutoff: 33.60 V (4.20 V/cell); Discharge cutoff: 22.40 V (2.80 V/cell); Maximum continuous discharge current: 14.55 A; Total pack energy capacity: ~290 Wh.</li>
      <li><strong>Hardware Sensing & BMS Interface:</strong> An industrial JBD smart BMS board connects directly to the battery pack, reading individual cell voltages via balance taps and pack thermal distribution via four NTC thermistors.</li>
      <li><strong>Edge Gateway Implementation (<code>bms_bluetooth_gateway.py</code>):</strong>
        <ul>
          <li>Connects over Bluetooth Low Energy (BLE) to the BMS GATT UART service and queries telemetry registers at 1.0–2.0 Hz.</li>
          <li>Parses raw hex payloads (commands 0x03 and 0x04) to unpack 8 individual cell voltages (mV precision), pack voltage, current, Coulomb-counted state-of-charge (SOC), and 4 temperature channels.</li>
          <li>Maintains local offline fault-tolerance by streaming telemetry into continuous local CSV and Excel logs (<code>bms_local_telemetry_log.csv</code>).</li>
          <li>Forwards validated JSON frames to the cloud API endpoint over HTTPS with token-based authentication.</li>
        </ul>
      </li>
    </ul>

    <div class="sec-heading">3. Dual-Layer Hybrid Inference Engine (Physics + ML)</div>
    <ul>
      <li><strong>Layer 1 &mdash; Deterministic Physics Guard:</strong>
        <ul>
          <li><strong>Dynamic Vehicle Operating Mode Classification:</strong> Implements thresholded current-velocity logic to partition pack states into IDLE, ACCELERATION, CRUISING, and REGENERATION/DECELERATION.</li>
          <li><strong>True Cell Vector Integrity:</strong> Continuously monitors all 8 individual cell channels without filtering or artificial mean-padding. Immediately flags sensor wire disconnections or dead cells (e.g., 0.015 V cell dropout).</li>
          <li><strong>Deterministic Threshold Verification:</strong> Evaluates active cell spread (&Delta;V), absolute voltage extremes, high charging rates, and continuous current draw against datasheet specifications.</li>
        </ul>
      </li>
      <li><strong>Layer 2 &mdash; Multi-Class XGBoost Time-Series Model:</strong>
        <ul>
          <li>Ingests a sliding 60-second telemetry window (60 historical time steps) to analyze time-series battery dynamics.</li>
          <li>Extracts 28 physical features, including first derivatives (dV/dt, dI/dt, dT/dt), 10-sample rolling standard deviations (&sigma;<sub>V</sub>, &sigma;<sub>T</sub>), spatial thermal gradients (&Delta;T = max(NTC) - min(NTC)), and individual cell drop rates.</li>
          <li><strong>Out-of-Distribution (OOD) Envelope Guard:</strong> Flags telemetry frames that fall outside empirical training bounds, preventing false model classifications during rare transient events.</li>
        </ul>
      </li>
      <li><strong>Arbitration & Physics Override:</strong> The system enforces a hard deterministic priority rule. If the ML classifier outputs "Normal" but Layer 1 physical bounds are violated (e.g., &Delta;V &ge; 150 mV or cell voltage &le; 2.80 V), the decision engine executes an immediate <strong>CRITICAL override with 100% confidence</strong>, guaranteeing zero critical escapes.</li>
    </ul>
  </div>

  <div class="footer-text">
    <span>AI-PBMS Technical Project Report &middot; Team ANS_4X (PSG iTech)</span>
    <span>Page 1 of 2</span>
  </div>
</div>

<!-- ==================== PAGE 2 ==================== -->
<div class="page">
  <div>
    <div class="doc-header">
      <div class="doc-title">Design and Implementation of an Intelligent Battery Management System (AI-PBMS)</div>
      <div class="doc-subtitle">Fault Progression Matrix, Safety Alerting Pipeline & Experimental Validation</div>
      <div class="doc-meta">Team ANS_4X &middot; PSG Institute of Technology and Applied Research (PSG iTech)</div>
    </div>

    <div class="sec-heading">4. Three-Phase Fault Progression & Threshold Matrix</div>
    <p style="font-size:8.3pt; margin-bottom:2px;">To enable early predictive intervention, all monitored faults are calibrated with a continuous 3-stage progression profile: <strong>Normal Baseline &rarr; Developing Risk (WARNING) &rarr; Critical Fault (CRITICAL)</strong>.</p>

    <table>
      <thead>
        <tr>
          <th style="width:23%;">Fault Classification</th>
          <th style="width:16%;">Normal Range</th>
          <th style="width:20%;">Stage 2: Risk (WARNING)</th>
          <th style="width:21%;">Stage 3: Fault (CRITICAL)</th>
          <th style="width:20%;">Corrective Action</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Cell Imbalance</strong></td>
          <td>&Delta;V &lt; 0.050 V</td>
          <td>&Delta;V &ge; 0.080 V (80 mV)</td>
          <td>&Delta;V &ge; 0.150 V (150 mV)</td>
          <td>Engage cell balancing; limit fast charge</td>
        </tr>
        <tr>
          <td><strong>Cell Undervoltage / Dropout</strong></td>
          <td>3.00 V – 4.15 V</td>
          <td>2.80 V &lt; V<sub>cell</sub> &le; 3.00 V</td>
          <td>V<sub>cell</sub> &le; 2.80 V (or 0 V dropout)</td>
          <td>Disconnect loads; isolate cell group</td>
        </tr>
        <tr>
          <td><strong>Cell Overvoltage</strong></td>
          <td>3.00 V – 4.15 V</td>
          <td>4.15 V &le; V<sub>cell</sub> &lt; 4.25 V</td>
          <td>V<sub>cell</sub> &ge; 4.25 V (V<sub>pack</sub> &ge; 33.6 V)</td>
          <td>Halt charging; isolate regen current</td>
        </tr>
        <tr>
          <td><strong>Overtemperature</strong></td>
          <td>20°C – 40°C</td>
          <td>45.0°C &le; T &lt; 55.0°C</td>
          <td>T &ge; 55.0°C (Emergency: 60.0°C)</td>
          <td>Activate cooling; reduce power demand</td>
        </tr>
        <tr>
          <td><strong>Continuous Overcurrent</strong></td>
          <td>-10 A to +10 A</td>
          <td>|I| &ge; 13.1 A (15.0 A)</td>
          <td>|I| &ge; 14.55 A (20.0 A)</td>
          <td>Trip main contactor; inspect busbars</td>
        </tr>
        <tr>
          <td><strong>Weak Cell Internal Resistance</strong></td>
          <td>&Delta;V<sub>sag</sub> &lt; 5%</td>
          <td>Voltage sag 20% &gt; baseline</td>
          <td>Voltage sag &ge; 40% &gt; baseline</td>
          <td>Log cell degradation; plan replacement</td>
        </tr>
      </tbody>
    </table>

    <div class="sec-heading">5. Automated Safety Alerting & Outbound Dispatch Architecture</div>
    <ul>
      <li><strong>Non-Blocking Background Worker Queue:</strong> Telemetry ingestion and inference execute on strict 100 ms timing. Alert evaluations pass tasks into an asynchronous <code>queue.Queue</code> managed by background daemon threads, preventing SMTP latency from stalling telemetry acquisition.</li>
      <li><strong>Dual-Path Alert Dispatch (Local Gateway + Cloud Server):</strong>
        <ul>
          <li>When running on the local edge hardware, the script dispatches outbound emails directly via local SMTP (<code>smtp.gmail.com:465</code> over SSL), completely avoiding cloud datacenter IP blocks.</li>
          <li><strong>Zero-Delay Escalation Logic:</strong> Standard alerts use a 20-second cooldown per fault to avoid flooding. However, if a state escalates from WARNING to CRITICAL, cooldown is bypassed immediately to send an urgent notification within 1 second.</li>
          <li><strong>Forensic Data Attachment:</strong> Each outbound email includes the exact triggering parameter, timestamp, pack voltage, current, temperatures, all 8 cell voltages, and an auto-generated CSV attachment containing the last 10 telemetry rows leading up to the fault.</li>
        </ul>
      </li>
    </ul>

    <div class="sec-heading">6. Real-Time Telemetry Dashboard & Interactive Demonstration</div>
    <ul>
      <li><strong>Live Web Interface (<code>live_dashboard_v3.html</code>):</strong> Displays the battery state with clear status badges (NORMAL / WARNING / CRITICAL), an 8-cell voltage grid, Coulomb-counted SOC, thermal channel readings, and a dynamic 50-event historical alert table with resolution timestamps.</li>
      <li><strong>Acoustic Alarm System:</strong> Incorporates the browser Web Audio API to emit warning beeps during Stage 2 risks and continuous siren alarms during Stage 3 critical faults until acknowledged by the operator.</li>
      <li><strong>Fault Replay Demonstrator (<code>run_dashboard_demo.py</code>):</strong> An interactive orchestrator that streams real labeled datasets to showcase system response across individual faults:
        [1] Normal baseline, [2] Cell Imbalance, [3] Weak Cell, [4] Overvoltage, [5] Undervoltage, [6] Overtemperature, and [7] Mixed Full-Cycle (595 rows, ~5 minutes).
      </li>
    </ul>

    <div class="sec-heading">7. Experimental Results & Engineering Conclusions</div>
    <ul>
      <li><strong>Fault Response Time:</strong> Severe cell dropouts, overcurrent spikes, and disconnected balance leads are recognized and isolated in under 500 ms.</li>
      <li><strong>Predictive Accuracy:</strong> The dual-layer hybrid architecture demonstrated a 98.5% classification accuracy across augmented real-world drive cycles while eliminating critical false-negative escapes.</li>
      <li><strong>Robustness & Portability:</strong> The platform operates fully autonomously on edge hardware (Raspberry Pi) and supports dynamic parameter updates for NMC, LiFePO4, and LTO chemistries via external configuration profiles.</li>
    </ul>
  </div>

  <div class="footer-text">
    <span>AI-PBMS Technical Project Report &middot; Team ANS_4X (PSG iTech)</span>
    <span>Page 2 of 2</span>
  </div>
</div>

</body>
</html>
"""

def generate():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(project_root, 'AI_PBMS_Report_BW.html')
    pdf_path = os.path.join(project_root, 'AI_PBMS_Project_Report.pdf')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Wrote clean B&W HTML: {html_path}")

    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    ]
    browser_exe = None
    for cand in edge_candidates:
        if os.path.exists(cand):
            browser_exe = cand
            break

    if not browser_exe:
        raise FileNotFoundError("Browser executable not found.")

    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(pdf_path):
        print(f"PDF creation error: {res.stderr}")
        return

    # Check pages
    reader = pypdf.PdfReader(pdf_path)
    page_count = len(reader.pages)
    print(f"Generated PDF: {pdf_path} | Size: {os.path.getsize(pdf_path)/1024:.1f} KB | Pages: {page_count}")

    # Copy directly to Downloads folder
    dl_dir = r"C:\Users\aksha\Downloads"
    if os.path.exists(dl_dir):
        # 1. Primary destination
        dl_report = os.path.join(dl_dir, "AI_PBMS_Project_Report.pdf")
        shutil.copy2(pdf_path, dl_report)
        print(f"Copied clean B&W PDF to Downloads: {dl_report}")

        # 2. Also try copying to AI_PBMS_2Page_WriteUp.pdf if not locked
        dl_writeup = os.path.join(dl_dir, "AI_PBMS_2Page_WriteUp.pdf")
        try:
            shutil.copy2(pdf_path, dl_writeup)
            print(f"Updated {dl_writeup}")
        except Exception as e:
            print(f"Note: {dl_writeup} is currently open by viewer (skipping overwrite). You can access {dl_report}.")

    # Copy to artifacts dir
    artifact_dir = r"C:\Users\aksha\.gemini\antigravity\brain\66ab0a10-e4aa-4cc2-b462-f1207abb9a32"
    if os.path.exists(artifact_dir):
        shutil.copy2(pdf_path, os.path.join(artifact_dir, "AI_PBMS_Project_Report.pdf"))
        print("Updated PDF in artifact directory.")

if __name__ == "__main__":
    generate()
