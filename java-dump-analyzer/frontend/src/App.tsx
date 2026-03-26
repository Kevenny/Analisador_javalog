import { BrowserRouter, Route, Routes } from "react-router-dom";
import Analysis from "./pages/Analysis";
import Home from "./pages/Home";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <a href="/" className="text-xl font-bold text-blue-700 hover:text-blue-800">
              Java Dump Analyzer
            </a>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/analysis/:id" element={<Analysis />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
