import React, { useState } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import Overview from './pages/Overview';
import Investigations from './pages/Investigations';
import RiskClusters from './pages/RiskClusters';
import Transactions from './pages/Transactions';
import ModelIntelligence from './pages/ModelIntelligence';
import SystemArchitecture from './pages/SystemArchitecture';

export default function App() {
  const [currentPage, setCurrentPage] = useState('overview');
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [selectedClusterId, setSelectedClusterId] = useState(null);

  const handleSearchAccount = (accountId) => {
    setSelectedAccountId(accountId);
    setCurrentPage('investigations');
  };

  const handleSelectAccount = (accountId) => {
    setSelectedAccountId(accountId);
  };

  const handleSelectCluster = (clusterId) => {
    setSelectedClusterId(clusterId);
  };

  return (
    <div className="min-h-screen bg-[#090D16] text-[#F8FAFC] flex font-sans">
      {/* Fixed Left Sidebar */}
      <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />

      {/* Main Content Area */}
      <div className="flex-1 ml-64 flex flex-col min-h-screen">
        {/* Fixed Top Bar */}
        <TopBar onSearchAccount={handleSearchAccount} highRiskCount={233} />

        {/* Page Content View */}
        <main className="flex-1 mt-14 px-8 py-6 max-w-7xl w-full mx-auto">
          {currentPage === 'overview' && (
            <Overview
              onNavigate={setCurrentPage}
              onSelectAccount={handleSelectAccount}
              onSelectCluster={handleSelectCluster}
            />
          )}

          {currentPage === 'investigations' && (
            <Investigations
              selectedAccountId={selectedAccountId}
              onSelectAccount={handleSelectAccount}
              onNavigate={setCurrentPage}
            />
          )}

          {currentPage === 'clusters' && (
            <RiskClusters
              selectedClusterId={selectedClusterId}
              onSelectCluster={handleSelectCluster}
              onSelectAccount={handleSelectAccount}
              onNavigate={setCurrentPage}
            />
          )}

          {currentPage === 'transactions' && (
            <Transactions
              onSelectAccount={handleSelectAccount}
              onNavigate={setCurrentPage}
            />
          )}

          {currentPage === 'models' && <ModelIntelligence />}

          {currentPage === 'system' && <SystemArchitecture />}
        </main>
      </div>
    </div>
  );
}
