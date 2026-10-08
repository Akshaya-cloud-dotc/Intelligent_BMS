import os
import subprocess
import shutil
import pypdf

html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>AI-PBMS Application & Field Deployment Report</title>
<style>
  @page {
    size: A4 portrait;
    margin: 10mm 15mm 9mm 15mm;
  }
  * {
    box-sizing: border-box;
  }
  body {
    font-family: 'Times New Roman', Times, serif;
    color: #000000;
    line-height: 1.27;
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
  
  /* Academic / Industrial Report Header */
  .doc-header {
    text-align: center;
    border-bottom: 1.2pt solid #000000;
    padding-bottom: 5px;
    margin-bottom: 6px;
  }
  .doc-title {
    font-size: 13pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.2px;
    margin-bottom: 2px;
  }
  .doc-subtitle {
    font-size: 9.3pt;
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
    margin: 2px 0 3px 0;
    text-align: justify;
  }

  ul {
    margin: 1.5px 0 3.5px 0;
    padding-left: 16px;
  }

  li {
    margin-bottom: 1.5px;
    text-align: justify;
  }

  /* Academic Booktabs Table Style */
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.9pt;
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
      <div class="doc-title">Intelligent Battery Management System (AI-PBMS)</div>
      <div class="doc-subtitle">Industrial Applications, Field Operational Architecture & Commercial Deployment</div>
      <div class="doc-meta">Team ANS_4X &middot; PSG Institute of Technology and Applied Research (PSG iTech)</div>
    </div>

    <div class="sec-heading">1. Industrial Problem Statement & Real-World Motivation</div>
    <ul>
      <li><strong>The Limitations of Traditional BMS in the Field:</strong> Conventional commercial BMS units act only as reactive fuses&mdash;they disconnect loads only <em>after</em> a cell drops below 2.80V or exceeds 55&deg;C. In commercial operations, this results in sudden mid-trip vehicle strandings, unpredicted battery fires in depots, and accelerated degradation without warning.</li>
      <li><strong>Fleet Operational Blindspots:</strong> Fleet managers lack actionable insight into individual cell health and impending failures. When a single weak cell degrades inside an 8S2P pack, the entire vehicle suffers reduced range, yet depot technicians cannot diagnose the root cause until the pack completely dies.</li>
      <li><strong>The AI-PBMS Value Proposition:</strong> An edge-integrated, physics-informed AI system that predicts impending battery failures <strong>30 to 90 seconds in advance</strong>, enabling automated graceful power derating, driver early warnings, and zero-downtime maintenance dispatch.</li>
    </ul>

    <div class="sec-heading">2. Target Industrial Applications & Use Cases</div>
    <ul>
      <li><strong>Commercial Electric Vehicle Fleets (2W / 3W Logistics & Last-Mile Delivery):</strong>
        <ul>
          <li><em>Preventing Mid-Route Vehicle Strandings:</em> Identifies high-impedance weak cells that sag under sudden hill-climbing or heavy acceleration, alerting dispatch to reroute before the vehicle stalls.</li>
          <li><em>Intelligent Dynamic Power Derating:</em> Instead of abruptly cutting traction power on busy roads, the system communicates with motor controllers to restrict peak draw, allowing safe transit to the nearest service hub.</li>
        </ul>
      </li>
      <li><strong>Battery Swapping Stations & Automated Health Screening:</strong>
        <ul>
          <li><em>Instant Pre-Charge Quarantine:</em> Automatically screens returning swapped packs for internal thermal gradients (&Delta;T &gt; 5&deg;C) or cell imbalance (&Delta;V &ge; 80 mV), isolating risky packs before fast-charging.</li>
          <li><em>Degradation-Based Pack Allocation:</em> Allocates healthier packs to high-demand commercial delivery riders while reserving partially degraded packs for low-speed, localized usage.</li>
        </ul>
      </li>
      <li><strong>Stationary Energy Storage Systems (BESS) & Solar Microgrids:</strong>
        <ul>
          <li><em>Depot & Solar Storage Protection:</em> Mitigates catastrophic thermal runaway by flagging anomalous heat generation hours before conventional smoke or bimetallic heat sensors trip.</li>
          <li><em>Active Operational Equalization:</em> Identifies unevenly aging series blocks to schedule preventive module re-balancing during non-peak solar hours.</li>
        </ul>
      </li>
      <li><strong>Circular Economy & Second-Life Battery Repurposing:</strong>
        <ul>
          <li><em>Automated Cell Health Grading:</em> Uses recorded driving cycle dynamic impedance signatures to classify retired EV battery modules for second-life residential backup without expensive laboratory teardowns.</li>
        </ul>
      </li>
    </ul>

    <div class="sec-heading">3. End-to-End Field Operational Architecture</div>
    <ul>
      <li><strong>Physical Battery Integration:</strong> Designed for 8S2P Li-ion packs (LG INR21700-M50 NMC cells, 29.04V nominal, 10 Ah, ~290 Wh) equipped with industrial JBD balance wiring harnesses and 4 surface-mounted thermal probes.</li>
      <li><strong>Rugged Edge Gateway Telematics (Raspberry Pi / On-Board Unit):</strong>
        <ul>
          <li><em>Continuous Bluetooth Telemetry:</em> Connects wirelessly over BLE to the BMS interface at 1.0&ndash;2.0 Hz, reading 8 cell voltages, current, SOC, and temperatures without bulky communication wiring.</li>
          <li><em>Autonomous Offline Edge Resilience:</em> Operates fully independently of internet access. If a vehicle enters underground parking, tunnels, or rural dead-zones, telemetry logs continuously to local non-volatile storage (<code>bms_local_telemetry_log.csv</code>), and local physical acoustic alarms remain active.</li>
        </ul>
      </li>
      <li><strong>Dual-Layer Decision Flow:</strong> Real-time edge inference runs locally on the vehicle. Predictive ML models identify early anomalous trajectories, while hard Layer 1 physical safety logic guarantees immediate contactor disconnect if limits are violated.</li>
    </ul>
  </div>

  <div class="footer-text">
    <span>AI-PBMS Application & Field Deployment Report &middot; Team ANS_4X (PSG iTech)</span>
    <span>Page 1 of 2</span>
  </div>
</div>

<!-- ==================== PAGE 2 ==================== -->
<div class="page">
  <div>
    <div class="doc-header">
      <div class="doc-title">Intelligent Battery Management System (AI-PBMS)</div>
      <div class="doc-subtitle">Operational Failure Remediation, Automated Dispatch Workflow & Economic Impact</div>
      <div class="doc-meta">Team ANS_4X &middot; PSG Institute of Technology and Applied Research (PSG iTech)</div>
    </div>

    <div class="sec-heading">4. Field Failure Scenarios & Practical Remediation Matrix</div>
    <p style="font-size:8.3pt; margin-bottom:2px;">How the AI-PBMS translates live predictive anomaly detection into actionable operational workflows in real-world fleet environments:</p>

    <table>
      <thead>
        <tr>
          <th style="width:20%;">Field Failure Scenario</th>
          <th style="width:25%;">Real-World Operational Risk</th>
          <th style="width:27%;">AI-PBMS Early Predictive Action</th>
          <th style="width:28%;">Field Maintenance & Fleet Response</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Weak Cell Under Load (High Impedance)</strong></td>
          <td>Vehicle abruptly shuts down during high-load acceleration or steep incline, stranding goods.</td>
          <td>Detects asymmetric dynamic sag (&gt;20% vs pack) during acceleration pulses 60s ahead of cutoff.</td>
          <td>Signals motor controller for graceful limp-home power limit; automatically tickets module for replacement.</td>
        </tr>
        <tr>
          <td><strong>Developing Cell Imbalance</strong></td>
          <td>Premature vehicle range loss; early termination of charge cycles; accelerated cell degradation.</td>
          <td>Flags progressive divergence rate d(&Delta;V)/dt at 80 mV spread during driving transitions.</td>
          <td>Schedules automated overnight active balancing cycle at depot; prevents premature pack scrapping.</td>
        </tr>
        <tr>
          <td><strong>Charging Thermal Runaway Risk</strong></td>
          <td>Localized hot-spot during fast charging triggers fire in parking garage or fleet depot.</td>
          <td>Identifies rapid dT/dt rise &gt;0.1&deg;C/s and spatial gradient &Delta;T &gt; 5&deg;C 90s before critical thermal trip.</td>
          <td>Immediately throttles charger current, sounds local acoustic siren, and dispatches SMS/email to depot safety crew.</td>
        </tr>
        <tr>
          <td><strong>Regenerative Braking Overvoltage</strong></td>
          <td>Downhill braking at 100% SOC forces lithium plating, internal shorts, and permanent pack death.</td>
          <td>Projects dV/dt trajectory near 4.20V/cell; warns that charge acceptance limit is being exceeded.</td>
          <td>Dynamically tapers regenerative braking torque; safely dissipates surplus kinetic energy into mechanical brakes.</td>
        </tr>
        <tr>
          <td><strong>Impending Deep Overdischarge</strong></td>
          <td>Battery completely drained to 0% on delivery route, causing copper dissolution and total pack ruin.</td>
          <td>Detects non-linear knee-point voltage collapse 60s prior to hard 2.80V cutoff.</td>
          <td>Prompts driver with audible alert to pull over safely; navigates vehicle to nearest charging kiosk.</td>
        </tr>
        <tr>
          <td><strong>Harness / Wire Disconnection</strong></td>
          <td>Vibration on bumpy roads causes balance tap pin disconnect; conventional BMS falsely trips as dead cell.</td>
          <td>Validates step-drop to 0V against current; recognizes non-physical open-circuit discontinuity.</td>
          <td>Pinpoints exact disconnected balance wire channel in diagnostics alert, slashing technician troubleshooting to minutes.</td>
        </tr>
      </tbody>
    </table>

    <div class="sec-heading">5. Automated Field Alerting & Maintenance Dispatch Workflow</div>
    <ul>
      <li><strong>Three-Tiered Alert Escalation:</strong>
        <ul>
          <li><em>Tier 1 (Vehicle Driver / Operator):</em> Real-time acoustic warning beeps and visual dashboard banner indicating status (NORMAL / WARNING / CRITICAL) and actionable advice (e.g. "Reduce Speed - Limp Home Mode Engaged").</li>
          <li><em>Tier 2 (Depot Service Team):</em> Direct local SMTP email dispatch (<code>smtp.gmail.com:465</code> over SSL) dispatched in &lt;1 second, containing fault classification, live driving mode, and an <strong>attached CSV snapshot of the last 10 telemetry rows</strong>.</li>
          <li><em>Tier 3 (Central Fleet Cloud Operations):</em> Live dashboard stream over HTTPS displaying fleet-wide pack status, health scores, and historical incident logs.</li>
        </ul>
      </li>
      <li><strong>Zero Interruption to Vehicle Telematics:</strong> Multi-threaded non-blocking queue (<code>queue.Queue</code>) offloads notification tasks so high-frequency sensor sampling and safety control never stall during network handshakes.</li>
    </ul>

    <div class="sec-heading">6. Commercial & Economic Impact (ROI for Fleet Operators & OEMs)</div>
    <ul>
      <li><strong>Elimination of Catastrophic Fire Risk:</strong> 30&ndash;90 seconds of advance predictive warning allows active thermal mitigation and safe passenger egress before hazardous thermal runaway can initiate.</li>
      <li><strong>Up to 40% Reduction in Unscheduled Roadside Downtime:</strong> Shifts maintenance from reactive roadside towing to scheduled off-hours cell replacement at the depot.</li>
      <li><strong>15&ndash;25% Extended Usable Battery Life:</strong> Mitigating micro-overcharging, aggressive deep discharge knees, and extreme thermal gradients preserves cell active material and slows irreversible capacity fade.</li>
      <li><strong>Transparent Warranty & Insurer Auditing:</strong> The automated 10-row black-box forensic snapshot provides irrefutable evidence of operating conditions during fault events, preventing fraudulent warranty claims and lowering fleet insurance premiums.</li>
    </ul>
  </div>

  <div class="footer-text">
    <span>AI-PBMS Application & Field Deployment Report &middot; Team ANS_4X (PSG iTech)</span>
    <span>Page 2 of 2</span>
  </div>
</div>

</body>
</html>
"""

def generate():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(project_root, 'AI_PBMS_Application_Report.html')
    pdf_path = os.path.join(project_root, 'AI_PBMS_Application_Report.pdf')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Wrote Application Report HTML: {html_path}")

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

    # Copy to Downloads folder
    dl_dir = r"C:\Users\aksha\Downloads"
    if os.path.exists(dl_dir):
        destinations = [
            os.path.join(dl_dir, "AI_PBMS_Application_Report.pdf"),
            os.path.join(dl_dir, "AI_PBMS_2Page_Application_WriteUp.pdf")
        ]
        for dst in destinations:
            try:
                shutil.copy2(pdf_path, dst)
                print(f"Successfully copied PDF to: {dst}")
            except PermissionError:
                print(f"Notice: {dst} is currently locked by a viewer. Skipped overwrite.")
            except Exception as e:
                print(f"Error copying to {dst}: {e}")

    # Copy to artifacts dir
    artifact_dir = r"C:\Users\aksha\.gemini\antigravity\brain\66ab0a10-e4aa-4cc2-b462-f1207abb9a32"
    if os.path.exists(artifact_dir):
        for art_name in ["AI_PBMS_Application_Report.pdf", "AI_PBMS_2Page_Application_WriteUp.pdf"]:
            try:
                shutil.copy2(pdf_path, os.path.join(artifact_dir, art_name))
                print(f"Updated {art_name} in artifact directory.")
            except Exception as e:
                print(f"Error copying artifact {art_name}: {e}")

if __name__ == "__main__":
    generate()
