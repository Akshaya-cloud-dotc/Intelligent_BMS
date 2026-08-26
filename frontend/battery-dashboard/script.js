document.addEventListener('DOMContentLoaded', () => {
    const uploadBox = document.getElementById('uploadBox');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileNameDisplay = document.getElementById('fileName');
    const removeFileBtn = document.getElementById('removeFileBtn');

    const seriesInput = document.getElementById('seriesInput');
    const parallelInput = document.getElementById('parallelInput');

    // Display elements
    const cellVoltageEl = document.getElementById('cellVoltage');
    const cellMaxVoltageEl = document.getElementById('cellMaxVoltage');
    const cellMaxCurrentEl = document.getElementById('cellMaxCurrent');
    const cellMaxTempEl = document.getElementById('cellMaxTemp');

    const packOvervoltageEl = document.getElementById('packOvervoltage');
    const packOvercurrentEl = document.getElementById('packOvercurrent');
    const packOvertempEl = document.getElementById('packOvertemp');

    const cellDataOverlay = document.getElementById('cellDataOverlay');
    const packDataOverlay = document.getElementById('packDataOverlay');

    // Simulated cell parameters (in a real app, this would come from backend PDF parsing)
    let extractedCellData = null;

    // --- File Upload Handling ---

    uploadBox.addEventListener('click', () => {
        fileInput.click();
    });

    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadBox.classList.add('dragover');
    });

    uploadBox.addEventListener('dragleave', () => {
        uploadBox.classList.remove('dragover');
    });

    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadBox.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    removeFileBtn.addEventListener('click', () => {
        resetData();
    });

    function handleFile(file) {
        fileNameDisplay.textContent = file.name;
        uploadBox.style.display = 'none';
        fileInfo.classList.remove('hidden');
        
        // Simulate extraction delay
        setTimeout(() => {
            simulateExtraction();
        }, 800);
    }

    function resetData() {
        fileInput.value = '';
        uploadBox.style.display = 'flex';
        fileInfo.classList.add('hidden');
        extractedCellData = null;
        updateUI();
    }

    // --- Logic & Calculations ---

    function simulateExtraction() {
        // Mock data extracted from a typical Li-ion 18650 cell datasheet
        extractedCellData = {
            nominalVoltage: 3.7, // V
            maxVoltage: 4.2,     // V
            maxCurrent: 10,      // A (Continuous Discharge)
            maxTemp: 60          // °C
        };
        updateUI();
    }

    function updateUI() {
        if (!extractedCellData) {
            cellDataOverlay.classList.remove('hidden');
            packDataOverlay.classList.remove('hidden');
            return;
        }

        // Hide overlays
        cellDataOverlay.classList.add('hidden');
        packDataOverlay.classList.add('hidden');

        // Update Cell UI
        cellVoltageEl.textContent = `${extractedCellData.nominalVoltage.toFixed(2)} V`;
        cellMaxVoltageEl.textContent = `${extractedCellData.maxVoltage.toFixed(2)} V`;
        cellMaxCurrentEl.textContent = `${extractedCellData.maxCurrent.toFixed(2)} A`;
        cellMaxTempEl.textContent = `${extractedCellData.maxTemp} °C`;

        calculatePackThresholds();
    }

    function calculatePackThresholds() {
        if (!extractedCellData) return;

        const series = parseInt(seriesInput.value) || 1;
        const parallel = parseInt(parallelInput.value) || 1;

        // User requested logic:
        // max voltage is the max voltage of the cell times no. of cells in series.
        // max current is the max current of the cell time no. of cells in parlell
        
        const packMaxVoltage = extractedCellData.maxVoltage * series;
        const packMaxCurrent = extractedCellData.maxCurrent * parallel;
        // Overtemperature threshold is usually dependent on cell chemistry and doesn't multiply
        const packMaxTemp = extractedCellData.maxTemp;

        // Update Pack UI
        packOvervoltageEl.textContent = `${packMaxVoltage.toFixed(2)} V`;
        packOvercurrentEl.textContent = `${packMaxCurrent.toFixed(2)} A`;
        packOvertempEl.textContent = `${packMaxTemp} °C`;
    }

    // Listen for changes in Series and Parallel inputs
    seriesInput.addEventListener('input', calculatePackThresholds);
    parallelInput.addEventListener('input', calculatePackThresholds);
});
