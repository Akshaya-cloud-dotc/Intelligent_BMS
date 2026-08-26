
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import BatteryDashboard from './pages/BatteryDashboard';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/configurator" element={<BatteryDashboard />} />
      </Routes>
    </Router>
  );
}

export default App;
